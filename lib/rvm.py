from os import *
from my_commands import Commands

from base import Base

from buildbot.steps import shell
from buildbot.process.properties import Property
from buildbot.steps.transfer import StringDownload
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
    def __init__(self, ruby_version='1.8.7-p302', gemset='', modules={}, vm=None, **kwargs):
        self.ruby_version      = ruby_version
        self.gemset            = gemset
        self.modules           = modules
        self.vm                = vm
#        self.name              = 'RVM ' + self.ruby_version + '@' + self.gemset
        self.name              = 'RVM'
        self.ruby_version_base = '1.8.7-p302' # default debian version.
        self.commands          = RvmCommands(ruby_version=ruby_version, gemset=gemset, vm = vm)
        self.is_vm = False
        Base.__init__(self, vm, **kwargs)

    def install_packages(self):
        # assumes puppet, debian style or pkg_add.
        self.addCommandIfBasic(
            command = [ 'bash', '-c',
                        ' '.join(['sudo', 'apt-get','update',';',
                                  'sudo', 'puppet', 'apply', '-e',\
                                      "'package {curl: ensure => present;bzip2: "+\
                                      "ensure => present }'", '||',
                                  'sudo', 'apt-get', 'install', 'curl', 'bzip2',\
                                      '-y' '||',
                                  'sudo', 'pkg_add', '-rv', 'curl' ])],
            property_name   = self.name,
            descriptionDone = 'Pre-pkgs installed',
            description     = 'Installing pre-pkgs')

        command = ['bash', '-c', 'bash -s stable < '+
                   '<(curl -s https://raw.github.com/wayneeseguin/rvm/master/'+\
                       'binscripts/rvm-installer 2>/dev/null);' + \
                       "id | grep -q root && mkdir -p /root/.rvm/ && "+\
                       "cp -a /usr/local/rvm/* /root/.rvm/;" +\
                       "sudo bash -s < <(source ~/.rvm/scripts/rvm; "+\
                       "rvm requirements 2>&1 | grep ' ruby:.*install' | "+\
                       "cut -d: -f2 | sed -Ee 's/(.*)/\\1 -y/'); "+\
                       "bash -c source ~/.rvm/scripts/rvm; "+\
                       "rvm install " + self.ruby_version_base]

        self.addCommandIfBasic(
            command = command,
            property_name = self.name,
            description = 'Installing RVM',
            descriptionDone = 'RVM')

        self.addCommandIfRaw(
            command = self.commands.base(
                [ 'rvm install '+self.ruby_version ], self.ruby_version_base ),
            property_name = self.name,
            description = 'Installing Ruby',
            descriptionDone = 'Ruby'+self.ruby_version)
                
        self.addCommandIfRaw(
            command = self.commands.base(
                [ 'rvm gemset list | egrep -q '+ \
                      self.gemset + ' || ' + \
                      'rvm gemset create '+self.gemset]),
            property_name = self.name,
            description = 'Creating Gemset',
            descriptionDone = 'Gemset',
            )
        # Adding all requested modules
        # TODO: should be an util: list2keys
        for mod in self.modules:    # a list to get thing in order.
            for tmp in mod.items(): # only one iteration
                module, version = tmp
            args = []
            if isinstance(version, types.ListType):
                args = version
                args.reverse()
                version = args.pop()
            self.addCommandIfRaw(
                description="Checking",
                descriptionDone=module,
                property_name = self.name,
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
