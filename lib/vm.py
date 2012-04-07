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
                 want_init_snap_named='__is_not_a_name',
                 vm = False,
                 root_vm_dir = '',
                 commands_class = '',
                 machine = False,
                 ):
        Base.__init__(self, commands = commands_class(machine = machine, basedir = self.basedir, vm = vm))
        cmds = commands_class(machine = machine, vm = vm, basedir = self.basedir)
        self.factory=factory
        self.vm = vm
        self.pre_commands_hook = []
        if want_init_snap_named == '__is_not_a_name':
            self.want_init_snap_named = 'initial_state-vm'+self.make_uniq_initial_name()
        self.want_init_snap_named = want_init_snap_named
        self.root_vm_dir = root_vm_dir

    def addUploadDirectory(self, src_dir, dst_dir):
        raise MyFactoryError("MyFactoryError must be provided to be able to upload to the VM")

    def addShellCmd(self, src_dir, dst_dir):
        raise MyFactoryError("addShellCmd must be provided to be able to exec on the VM")

    def start(self):
        if self.can_snap:
            property_name = self.want_init_snap_named

        if self.vm:
            self.vm.start()

        self.install_packages()
        self.install_vm()

        if self.can_snap:
            self.install_snap()

        self.start_vm()

        if self.can_snap:
            if self.want_init_snap_named:
                self.addTakeSnap('initial_state-vm'+self.make_uniq_initial_name()) # father of all snaps
                self.factory.addStep(shell.SetProperty(
                        command=self.vagrant_cmd.snap_exists(self.want_init_snap_named),
                        description='Setting property',
                        property=self.want_init_snap_named))


        if self.fix_network:
            self.fix_net()

        # http://www.python.org/dev/peps/pep-0322/
        while self.pre_commands_hook:
            command = self.pre_commands_hook.pop()
            self.addShellCmd(command, running = 'Running Pre-Hook', done='Pre-Hook',
                             dostep = lambda s,n=self.want_init_snap_named: s.getProperty(n, 'FALSE') == 'FALSE')

        if self.want_init_snap_named:
            self.addRevertToSnap(self.want_init_snap_named)
            if self.fix_network:
                self.fix_net

    def make_uniq_initial_name(self):
        vm = self.vm
        counter = 0
        while vm:
            vm = vm.vm
            counter += 1
        return str(counter)



