from os import *
import types

from my_commands import Commands
from base import Base

class DummyCommands(Commands):
    def __init__(self, directory='myenv', vm=None):
        Commands.__init__(self,vm)
        self.directory = directory

    def simple(self, cmd=[], workdir=None):
        cmd_tmp = ['source ' + self.directory + '/dummy', ';'] + \
                  [' '.join(cmd)]
        if workdir:
            cmd_tmp = ['cd', workdir, '&&'] + cmd_tmp
        command = self.basic(['bash', '-c', ] + [' '.join(cmd_tmp)])
        return command

    def check_or_install(self, module='', version='> 0', args = []):
        cmd = self.simple(['dummy', 'install'] +args+ [ module ] )
        return cmd

class Dummy(Base):
    def __init__(self, directory='', modules={}, vm=None, **kwargs):
        self.modules           = modules
        self.vm                = vm
        self.name              = directory +'@name'
        self.directory         = directory
        self.is_vm = False
        Base.__init__(self, vm, **kwargs)

    def init_command(self):
        self.commands = DummyCommands(
            directory = self.directory,
            vm = self.vm)

    def install_packages(self):
        self.addCommandIfBasic(
            command = ['bash', '-c'] +[
                ' '.join(['sudo', 'dummy', 'completeinstall'])]) 
        
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

    def addDummyCmd(self, command = [], **kwargs):
        self.addShellCmd(command = command, **kwargs)
