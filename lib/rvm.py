from os import *
from my_commands import Commands

from buildbot.steps import shell
from buildbot.process.properties import Property
from buildbot.steps.transfer import StringDownload
from buildbot.steps.shell import ShellCommand
from buildbot.steps.source import Git

class RvmCommands(Commands):
    def __init__(self, ruby_version='1.8.7-p302', gemset='', vm=False):
        Commands.__init__(self,vm)
        self.ruby_version = ruby_version
        self.gemset = gemset

    def simple(self, cmd=[], ruby_version = False):
        if not ruby_version:
            ruby_version = self.ruby_version
        command = ['bash', '-c', 'source ~/.rvm/scripts/rvm;' +
                   'rvm use ' + ruby_version + '; ' + ' '.join(cmd)]
        return self.basic(command)
        
    def create(self, cmd=[], sep=';'):
        command = self.simple(['rvm', 'use', self.ruby_version + '@' + self.gemset +'; ', ' '.join(cmd)])
        return command

    def check_or_install(self, module='', version='> 0'):
        cmd = self.create(['gem', 'list', '-i', module, '-v', "'"+version+"'", '||',
                           'gem', 'install', module, '-v', "'"+version+"'"])
        return cmd

class Rvm:
    def __init__(self, factory='', ruby_version='1.8.7-p302', gemset='', modules={}, vm=False):
        self.factory = factory
        self.ruby_version = ruby_version
        self.gemset = gemset
        self.modules = modules
        self.vm = vm
        self.ruby_version_base = '1.8.7-p302' # default debian version.
        self.rvmcommands = RvmCommands(ruby_version=ruby_version, gemset=gemset, vm = vm)

    def start(self):
        property_name = self.ruby_version + self.gemset
        if self.vm:             # assumes vagrant vm
            self.vm.add_pre_command([
                    [ 'sudo', 'puppet', 'apply', '-e', "'package {curl: ensure => present }'" ]
                    ])
            self.vm.init_snap(property_name)
            self.vm.start()
            
        self.factory.addStep(shell.SetProperty(
                command=self.rvmcommands.basic(['([ -e $HOME/.rvm/scripts/rvm ] && echo TRUE) || echo FALSE']),
                description='Setting property',
                doStepIf = lambda s, n=property_name: s.getProperty(n, 'FALSE') == 'FALSE',
                property='rvm_is_installed',
                ))

        # requires curl!
        command = ['bash', '-c', 'bash -s stable < '+
                   '<(curl -s https://raw.github.com/wayneeseguin/rvm/master/binscripts/rvm-installer 2>/dev/null) && ' + \
                       # TODO: Work only for debian style install 
                       "sudo bash -s < <(source ~/.rvm/scripts/rvm; rvm requirements 2>&1 | grep ' ruby:.*install' | cut -d: -f2 | sed -Ee 's/(.*)/\\1 -y/'); bash -c source ~/.rvm/scripts/rvm; rvm install "+
                   self.ruby_version_base]

        self.factory.addStep(ShellCommand(
                command = self.rvmcommands.basic(command),
                description = 'Installing RVM',
                descriptionDone = 'RVM',
                doStepIf = lambda s,n=property_name: s.getProperty('rvm_is_installed','FALSE') == 'FALSE' and s.getProperty(n, 'FALSE') == 'FALSE'))
        self.factory.addStep(ShellCommand(
                command = self.rvmcommands.simple(
                    [ 'rvm install '+self.ruby_version ], self.ruby_version_base ),
                description = 'Installing Ruby',
                descriptionDone = 'Ruby'+self.ruby_version,
                doStepIf = lambda s, n=property_name: s.getProperty(n, 'FALSE') == 'FALSE',))
                
        self.factory.addStep(ShellCommand(
                command = self.rvmcommands.simple([ 'rvm gemset list | egrep -q '+self.gemset + ' || ' + 'rvm gemset create '+self.gemset]),
                doStepIf = lambda s, n=property_name: s.getProperty(n, 'FALSE') == 'FALSE',
                description = 'Creating Gemset',
                descriptionDone = 'Gemset',
                ))

        for module, version in self.modules.iteritems():
            self.factory.addStep(ShellCommand(
                    doStepIf = lambda s, n=property_name: s.getProperty(n, 'FALSE') == 'FALSE',
                    description="Checking",
                    descriptionDone=module,
                    command=self.rvmcommands.check_or_install(module, version),
                    ))
        if self.vm:
            self.vm.addTakeSnap(property_name)

    def addRVMCmd(self, command = [],workdir='',description='Running', descriptionDone='Done'):
        self.factory.addStep(ShellCommand(
                description = description,
                descriptionDone = descriptionDone,
                command = self.rvmcommands.create(command)))

    def addRVMRakeCmd(self, command = '',workdir='',description='Running', descriptionDone='Done'):
        self.factory.addStep(ShellCommand(
                description = description,
                descriptionDone = descriptionDone,
                command = self.rvmcommands.create(cmd = ['rake', command])))
