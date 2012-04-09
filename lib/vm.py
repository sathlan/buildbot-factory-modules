# -*- python -*-
# ex: set syntax=python:

from os import *
import os.path
import string
import inspect

from base import Base
from error import MyFactoryError

from buildbot.steps import shell
from buildbot.process.properties import Property
from buildbot.steps.shell import ShellCommand
# the new version offers more choice for git, like keeping file from
# gitignore.
from buildbot.steps.source.git import Git
# Try schedule does not work with the new git module
# version 0.8.5 12/21/04
from buildbot.steps.source import Git as GitOld
from buildbot.steps.transfer import StringDownload

class Vm(Base):
    def __init__(self, 
                 factory = '',
                 want_init_snap = True,
                 init_snap_name = '',
                 vm = None,
                 root_vm_dir = '',
                 commands_class = '',
                 machine = False,
                 boxname = 'default',
                 ):
        Base.__init__(self, commands = \
                          commands_class(machine = machine, basedir = self.basedir, vm = vm),
                      vm = vm)
        cmds = commands_class(machine = machine, vm = vm, basedir = self.basedir)
        self.boxname = boxname
        self.factory=factory
        self.vm = vm
        self.is_vm = True
        self.pre_commands_hook = []
        if want_init_snap:
            if not init_snap_name:
                self.want_init_snap_named = self.make_uniq_initial_name()
        self.root_vm_dir = root_vm_dir

    def addUploadDirectory(self, src_dir, dst_dir):
        raise MyFactoryError("MyFactoryError must be provided to be able to upload to the VM")

    def addTakeSnap(self, snap_name='____non_exististing_snap'):
        # execute only on the hw node.
        vm = self
        while vm.vm:
            vm = vm.vm
        vm.addCommandIf(command = vm.commands.snap('take', snap_name),
                         true_or_false = 'FALSE',
                         property_name = snap_name,
                         description = 'Snapping',
                         descriptionDone = 'Snapped')

    def addRevertToSnap(self, snap_name='____non_exististing_snap', assume_exists = False):
        # execute only on the hw node.
        vm = self
        while vm.vm:
            vm = vm.vm
        cmd = vm.commands.snap('go',snap_name)
        t_or_f = 'TRUE'
        if assume_exists:
            t_or_f = 'FALSE'
        print 'DEBUGA!!!1'
        vm.addCommandIf(command = cmd,
                         true_or_false = t_or_f,
                         description = 'Reverting',
                         descriptionDone = 'Revert to ' + snap_name,
                         property_name = snap_name)

    def addDeleteSnap(self, snap_name='____non_exististing_snap'):
        # execute only on the hw node.
        vm = self
        while vm.vm:
            vm = vm.vm
        cmd = vm.commands.snap('delete',snap_name)
        vm.addCommandIf(command = cmd,
                         true_or_false = 'TRUE',
                         description = 'Deleting Snap',
                         descriptionDone = 'Snap Deleted' + snap_name,
                         property_name = snap_name)
        
    def addShellCmdInVm(self, command=[], **kwargs):
        cmd = self.commands.ssh(command)
        self.addShellCmdBasic(command = cmd, **kwargs)

    def addCommandInVmIf(self, command = [], true_or_false = 'FALSE',
                    property_name = '', doStepIf = False, **kwargs):
        description = 'Running Maybe'
        descriptionDone = 'Done Maybe'
        if 'description' in kwargs:
            description = kwargs['description']
        if 'descriptionDone' in kwargs:
            descriptionDone = kwargs['descriptionDone']
        doStepIf = lambda s, name=property_name,tf=true_or_false: \
            s.getProperty(name,'FALSE') == tf
        self.factory.addStep(ShellCommand(
                command = self.commands.ssh(command),
                doStepIf = doStepIf,
                **kwargs
                ))

    def addCpDirectoryInVm(self, src_dir, dst_dir):
        self.factory.addStep(ShellCommand(
            command = self.commands.ssh(['bash', '-c', ' '.join(['rm','-rf', dst_dir, '&&',
                           'mkdir', '-p', dst_dir, '&&', 
                           'cp', '-a',src_dir + '/*', dst_dir])]),
            description = 'Copying Dir in VM',
            descriptionDone = 'Dir Copied in VM'))

    def make_uniq_initial_name(self):
        vm = self.vm
        counter = 0
        while vm:
            vm = vm.vm
            counter += 1
        return self.boxname + '-' + str(counter)

    def init_snap(self, name=''):
        self.init_snap_name = name
