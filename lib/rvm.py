from os import *
from my_commands import Commands

from base import Base

from buildbot.steps import shell
from buildbot.process.properties import Property
from buildbot.steps.transfer import StringDownload
from buildbot.steps.shell import ShellCommand
from buildbot.steps.source import Git

import types

class RvmCommands(Commands):
    def __init__(self, ruby_version='1.8.7-p302', gemset='', vm=None):
        Commands.__init__(self,vm)
        self.ruby_version = ruby_version
        self.gemset = gemset

    def base(self, cmd=[], ruby_version = False):
        if not ruby_version:
            ruby_version = self.ruby_version
        command = ['bash', '-c', 'source ~/.rvm/scripts/rvm;' +
                   'rvm use ' + ruby_version + '; ' + ' '.join(cmd)]
        return self.basic(command)
        
    def simple(self, cmd=[], sep=';', workdir=None):
        cmd_tmp = ['rvm', 'use', self.ruby_version + '@' + self.gemset + sep, ' '.join(cmd)]
        if workdir:
            cmd_tmp = ['cd', workdir, '&&'] + cmd_tmp
        command = self.base(
            cmd = cmd_tmp,
            )
        return command

    def check_or_install(self, module='', version='> 0', args = []):
        cmd = self.simple(['gem', 'list', '-i', module, '-v', "'"+version+"'", '||',
                           'gem', 'install', module, '-v', "'"+version+"'",
                           '--conservative', '--no-ri', '--no-rdoc']+args)
        return cmd

class Rvm(Base):
    def __init__(self, factory='', ruby_version='1.8.7-p302', gemset='', modules={}, vm=None):
        self.factory = factory
        self.ruby_version = ruby_version
        self.gemset = gemset
        self.modules = modules
        self.vm = vm
        self.name = 'RVM'
        self.ruby_version_base = '1.8.7-p302' # default debian version.
        self.rvmcommands = RvmCommands(ruby_version=ruby_version, gemset=gemset, vm = vm)
        Base.__init__(self, self.rvmcommands, vm)

    def install_packages(self):
        # assumes puppet is present
        self.addShellCmdBasic(
            self.commands.basic([ 'sudo', 'puppet', 'apply', '-e', "'package {curl: ensure => present }'" ]))

        command = ['bash', '-c', 'bash -s stable < '+
                   '<(curl -s https://raw.github.com/wayneeseguin/rvm/master/binscripts/rvm-installer 2>/dev/null) && ' + \
                       # TODO: Work only for debian style install 
                   "sudo bash -s < <(source ~/.rvm/scripts/rvm; rvm requirements 2>&1 | grep ' ruby:.*install' | cut -d: -f2 | sed -Ee 's/(.*)/\\1 -y/'); bash -c source ~/.rvm/scripts/rvm; rvm install " +self.ruby_version_base]

        self.addShellCmdBasic(
            command = self.commands.basic(command),
            description = 'Installing RVM',
            descriptionDone = 'RVM')

        self.addShellCmdBasic(
            command = self.commands.base(
                [ 'rvm install '+self.ruby_version ], self.ruby_version_base ),
            description = 'Installing Ruby',
            descriptionDone = 'Ruby'+self.ruby_version)
                
        self.addShellCmdBasic(
            command = self.commands.base([ 'rvm gemset list | egrep -q '+ \
                                               self.gemset + ' || ' + \
                                               'rvm gemset create '+self.gemset]),
            description = 'Creating Gemset',
            descriptionDone = 'Gemset',
            )
        
       # TODO: should be an util: list2keys
        for mod in self.modules: # a list to get thing in order.
            for tmp in mod.items():      # only one iteration
                module, version = tmp
            args = []
            if isinstance(version, types.ListType):
                args = version
                args.reverse()
                version = args.pop()
            self.addShellCmdBasic(
                description="Checking",
                descriptionDone=module,
                command=self.commands.check_or_install(module, version, args))

    def addRVMCmd(self, command = [], **kwargs):
        self.addShellCmd(command = command, **kwargs)

    def addRVMRakeCmd(self, command = '',
                      description='Raking', descriptionDone='Rake', **kwargs):
        self.addShellCmd(
                description = description,
                descriptionDone = descriptionDone,
                command = ['rake', command],
                **kwargs)
