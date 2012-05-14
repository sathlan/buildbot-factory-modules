from os import *
import types

from my_commands import Commands
from vm          import Vm
from error       import VmError

class DummyVmCommands(Commands):
    def __init__(self, machine='test1_vm', vm=None):
        Commands.__init__(self,vm)
        self.machine = machine

    def simple(self, cmd=[], workdir=None):
        command =  self.basic(cmd)
        return command

    def ssh(self, cmd=[]):
        """ Execute command in the vm. """
        command = ['dummyvm', 'ssh']
        return self.simple(command + [' '.join(cmd)])

    def snap(self, command = '', snap_name = ''):
        cmd = ['test1_vm', 'snap', command]
        return cmd
    def snap_exists(self, snap = False):
        if snap:
            return [ 'bash', '-c', 'exit 0' ]
        else:
            return [ 'bash', '-c', 'exit 1' ]

    def up(self):
        cmd = ['test_vm', 'up']
        return self._around_command(cmd)
        
class DummyVm(Vm):
    def __init__(self, boxname='', vm=None, **kwargs):
        self.boxname           = boxname
        self.vm                = vm
        self.is_vm = False
        Vm.__init__(self, vm = vm, **kwargs)
        self.can_snap           = True
        self.property_exists    = self.name + '_EXI'
        self.property_run       = self.name + '_RUN'

        # The root VM should snap
        if self.run_on_vm:
            self.can_snap = False

    def init_command(self):
        self.commands = DummyVmCommands(machine = self.boxname, 
                                        vm = self.vm)

    def command_prefix(self, cmd = []):
        return self.commands.ssh(cmd)

    def install_packages(self):
        pass

    def install_vm(self):
        pass

    def start_vm(self):
        pass

    def install_snap(self):
        pass

    def addDownloadFileFromSocle(self, src_file, dst_file, workdir = '/',
                                 on_socle = False, as_root = False):
        pass

    def addDownloadDirectory(self, src_dir, dst_dir, as_root = False):
        pass

    def addTestVmCmd(self, command = [], **kwargs):
        self.addShellCmdInVm(command = command, **kwargs)

    def addCpFile(self, src_file, dst_file_final, as_root = True):
        super(Vm, self).addCpFile(src_file, dst_file_final, True)

    def addCpDirectory(self, src_file, dst_file_final, as_root = True):
        super(Vm, self).addCpDirectory(src_file, dst_file_final, True)

