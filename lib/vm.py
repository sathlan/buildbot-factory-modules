# -*- python -*-
# ex: set syntax=python:

from os import *
import os.path
import string
import inspect

from base import Base
from error import VmError

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
from buildbot.steps.transfer import FileDownload

class Vm(Base):
    """
    Base class for factory related to Virtual Machine.  This can be
    Vagrant, Openvz, ...

    Here are defined step specific to vm like :
    - taking snapshot;
    - reverting to snapshot;
    - executing command in the VM (as opposed to the directly 
      on the slave or the underlying vm)
    - downloading file/dir to the vm (as opposed to ...)
    """
    def __init__(self, 
                 want_init_snap = True,
                 init_snap_name = '',
                 vm = None,
                 root_vm_dir = '',
                 commands_class = '',
                 machine = False,
                 **kwargs):
        Base.__init__(self, vm = vm, **kwargs)
        self.vm                = vm
        self.is_vm             = True
        self.root_vm_dir       = root_vm_dir
        self.name              = self._make_uniq_initial_name()

    def addTakeSnap(self, snap_name='____non_exististing_snap'):
        """ Take a snap on the base vm.

        Use the X{take} subcommand of the X{snap} command of the module. 
        """
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
        """ Revert to a specific snapshot.  

        By default execute only if a property named as the snapshot
        exists.  This can be changed by setting the X{assume_exists}
        to X{True}.

        Use the subcommand X{go} of the X{snap} command.
        """
        # execute only on the hw node.
        vm = self
        while vm.vm:
            vm = vm.vm
        cmd = vm.commands.snap('go',snap_name)
        t_or_f = 'TRUE'
        assume = 'FALSE'
        if assume_exists:
            assume = 'TRUE'
        vm.addCommandIf(command = cmd,
                        true_or_false = t_or_f,
                        description = 'Reverting',
                        descriptionDone = 'Revert to ' + snap_name,
                        assume = assume,
                        property_name = snap_name)

    def addDeleteSnap(self, snap_name='____non_exististing_snap'):
        """ 
        Delete a snapshot.

        Use the subcommand X{delete} of the X{snap} command.
        """
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
        """
        Execute a command in the VM.

        Use the X{ssh} command.
        """
        cmd = self.commands.ssh(command)
        self.addShellCmdBasic(command = cmd, **kwargs)

    def addCommandInVmIf(self, command = [], true_or_false = 'FALSE',
                    property_name = '', doStepIf = False, **kwargs):
        """
        Add a command in the the VM only if a property is FALSE by
        default, assuming FALSE if the property is not set.

        This can be change by providing:
        - a lambda as a doStepIf;
        - true_or_false to TRUE to check for TRUE
        """
        description = 'Running Maybe'
        descriptionDone = 'Done Maybe'
        if 'description' in kwargs:
            description = kwargs['description']
        if 'descriptionDone' in kwargs:
            descriptionDone = kwargs['descriptionDone']
        doStepIf = lambda s, name=property_name,tf=true_or_false: \
            s.getProperty(name,'FALSE') == tf
        self.addStep(ShellCommand(
                haltOnFailure = True,
                command = self.commands.ssh(command),
                doStepIf = doStepIf,
                **kwargs
                ))

    def addCpDirectoryInVm(self, src_dir, dst_dir, as_root = False, **kwargs):
        """
        Copy a directory into the vm.

        By default execute the command as non root.  This can be
        changed using the X{as_root} parameter.
        """
        cmd = ['bash', '-c', 
               ' '.join(['rm','-rf', dst_dir, '&&',
                         'mkdir', '-p', dst_dir, '&&', 
                         'cp', '-a',src_dir + '/*', dst_dir])]
        if as_root:
            cmd = ['sudo'] + cmd
        self.addStep(ShellCommand(
                haltOnFailure = True,
                command = self.commands.ssh(cmd),
                description = 'Copying Dir in VM',
                descriptionDone = 'Dir Copied in VM',
                **kwargs))

    def addDownloadFileInVm(self, src_file = '', dst_file = '', workdir = '/', as_root = False):
        """
        Download a file or a string into the VM.

        It takes care of all underlying VM.  Check the
        L{_addDownloadFile} for the explanation.
        """
        self._addDownloadFile(src_file, dst_file, workdir, as_root)

    def addDownloadFile(self, src_file, dst_file, workdir = '/', as_root = False):
        """
        Download a file to the slave or the underlying vm, bringing
        the file at the same level as the vm (the "hardware" node).
        """
        if self.run_on_vm:
            self.vm.addDownloadFileInVm(src_file, dst_file, workdir, as_root)
        else:
            if not os.path.exists(src_file):
                self.addStep(StringDownload(s         = src_file,
                                            slavedest = dst_file))
            else:
                self.addStep(FileDownload(mastersrc = src_file,
                                          slavedest = dst_file))

    def addDownloadGitDirInVM(self, repo_url = '', dest_dir = '', mode='copy',
                              use_new = False, as_root = False, **kwargs):
        """
        Checkout/Patch the Git and download it into the vm.
        """
        self._addDownloadGitDir(repo_url, dest_dir, mode,
                                use_new, as_root, **kwargs)

    def addDownloadGitDir(self, repo_url = '', dest_dir = '', mode='copy',
                          use_new = False, as_root = False, **kwargs):
        """
        Checkout/Patch the Git and download it to the "hardware" node
        (the slave or the underlying vm)
        """
        if self.run_on_vm:
            self.vm._addDownloadGitDir(repo_url, dest_dir, mode, use_new, as_root, **kwargs)
        else:
            if use_new:
                self.addStep(Git(repourl=repo_url, mode='full', method='clean', 
                                 workdir = dest_dir, **kwargs))
            else:
                self.addStep(GitOld(repourl=repo_url, mode=mode, workdir = dest_dir, **kwargs))

    def _make_uniq_initial_name(self):
        """
        Make a unique L{name} for the vm from L{boxname}.
        """
        vm = self.vm
        counter = 0
        while vm:
            vm = vm.vm
            counter += 1
        return self.boxname + '-' + str(counter)
