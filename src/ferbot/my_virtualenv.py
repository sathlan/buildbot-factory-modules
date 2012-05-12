from os import *
from my_commands import Commands

from base import Base

from buildbot.steps import shell
from buildbot.process.properties import Property
from buildbot.steps.transfer import StringDownload
from buildbot.steps.source import Git

import types

class VirtualEnvCommands(Commands):
    def __init__(self, dir='myenv', gemset='', vm=None):
        Commands.__init__(self,vm)
        self.dir = dir

    def simple(self, cmd=[], workdir=None):
        cmd_tmp = ['source ' + self.dir + '/bin/activate', ';'] + \
                  [' '.join(cmd)]
        if workdir:
            cmd_tmp = ['cd', workdir, '&&'] + cmd_tmp
        command = self.basic(['bash', '-c', ] + [' '.join(cmd_tmp)])
        return command

    def check_or_install(self, module='', version='> 0', args = []):
        cmd = self.simple(['pip', 'install'] +args+ [ module ] )
        return cmd

class VirtEnv(Base):
    def __init__(self, env = '', dir='', modules={}, vm=None, **kwargs):
        self.modules           = modules
        self.vm                = vm
        self.name              = env
        self.env               = env
        self.is_vm = False
        Base.__init__(self, vm, **kwargs)

    def init_command(self):
        self.commands = VirtualEnvCommands(dir=self.env,
                                           vm = self.vm)


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
        self.addCommandIfBasic(
            command = ['bash', '-c'] +[
                ' '.join(['sudo', 'python', '<', 
                          '<(curl -s http://peak.telecommunity.com/dist/ez_setup.py);',
                          'sudo', 'easy_install', 'virtualenv', ';',
                          'virtualenv', '--no-site-packages', self.env, '|| exit 1 ;',
                          # make sqlite module works in freebsd, and
                          # no harm for other distribution
                          '( [ -e /usr/local/lib/python2.7/site-packages/_sqlite3.so ] && ' + \
                          'ln -s ' + \
                          '/usr/local/lib/python2.7/site-packages/_sqlite3.so '+\
                          self.env + '/lib/python2.7/ ) ' + '|| true']),],
            property_name = self.name,
            description = 'Installing VirtualEnv',
            descriptionDone = 'VirtualEnv')

        for mod in self.modules:    # a list to get thing in order.
            for tmp in mod.items(): # only one iteration
                module, version = tmp
            args = []
            v = version
            if isinstance(version, types.ListType):
                v = version[0]
                if len(version) > 1:
                    args = version[1:]
            self.addCommandIfRaw(
                description="Checking",
                descriptionDone=module,
                property_name = self.name,
                command=self.commands.check_or_install(module, v, args))

    def addVirtEnvCmd(self, command = [], **kwargs):
        self.addShellCmd(command = command, **kwargs)
