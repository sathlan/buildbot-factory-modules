# Try schedule does not work with the new git module
# version 0.8.5 12/21/04
from error import MyFactoryError

from buildbot.steps import shell

# Try schedule does not work with the new git module
# version 0.8.5 12/21/04
from buildbot.steps.source import Git as GitOld
# the new version offers more choice for git, like keeping file from
# gitignore.
from buildbot.steps.source.git import Git
# from buildbot.steps.slave import MakeDirectory # require buildbot 0.8.6!
from buildbot.steps.slave import RemoveDirectory
from buildbot.steps.shell import ShellCommand
from buildbot.steps.transfer import StringDownload
from buildbot.steps.transfer import FileDownload

import tempfile
import os.path

class Base():
    def __init__(self, commands = '', vm = None):
        self.commands = commands
        if vm:
            self.run_on_vm = True
        else:
            self.run_on_vm = False
        self.vm       = vm
        self.is_vm = False
        self.can_snap = False
        self.fix_network = False

    def start(self, quick = False, first = True):
        snapper = None
        if self.run_on_vm:
            snapper = self.vm.start(quick = quick, first = False)

        if self.is_vm and self.can_snap and not self.run_on_vm:
            snapper = self

        if snapper:
            if first: 
                snapper.addSetPropertyTF(
                    command = snapper.commands.snap_exists(self.name),
                    property = self.name)
        
        # assumes a restore to a snap will start the vm if it's stopped. 
        if not quick:
            self.install_packages()
            if self.is_vm:
                self.install_vm()

            if self.can_snap:
                self.install_snap()

            if self.is_vm:
                self.start_vm()

            if self.fix_network:
                self.fix_net()

        if snapper:
            snapper.start_quick(self.name, quick, first)
            if not quick:
                snapper.addTakeSnap(self.name)

        return snapper

    def start_quick(self, name, quick, first):
        if quick and first:
            self.addRevertToSnap(name)
            if self.fix_network:
                self.fix_net

    def addDownloadFile(self, src_file, dst_file, workdir = '/', steps = []):
        this_step = [self] + steps
        if self.run_on_vm:
            self.vm.addDownloadFile(src_file = src_file,
                                  dst_file = dst_file,
                                  workdir  = workdir,
                                  steps    = this_step)
        else:
            # "root" vm
            dst_file_rel = dst_file
            workdir_rel  = workdir
            if os.path.isabs(workdir):
                workdir_rel = os.path.relpath(workdir,'/')
            if os.path.isabs(dst_file):
                dst_file_rel = os.path.relpath(dst_file,'/')
            # workdir and all are for the final vm, here we assure
            # that the final file will be in 'build/<workdir>/<dst_file>
            dst_file_rel = os.path.join(workdir_rel, dst_file_rel)
            if not os.path.exists(src_file):
                self.factory.addStep(StringDownload(s         = src_file,
                                                    slavedest = dst_file_rel))
            else:
                self.factory.addStep(FileDownload(mastersrc = src_file,
                                                  slavedest = dst_file_rel))
            # now I deleguate the "upload" to each vm.
            iter_file = False
            last = len(this_step)
            cmpt = 1
            for step in this_step:
                final_dst = '/tmp'+ dst_file
                if cmpt == last:
                    final_dst = dst_file
                if not iter_file: # root vm
                    iter_file = step.addDownloadFileFromSocle(dst_file_rel, final_dst, workdir)
                else:           # itermediary vm
                    iter_file = step.addDownloadFileFromSocle(iter_file, final_dst, workdir)
                cmpt += 1

    def addDownloadGitDir(self, repo_url = '', dest_dir = '', mode='copy', use_new = False,
                        steps = []):
        """ Upload to a dir a Git(+patch) repository.  Support any number of underlying VM """
        this_step = [self] + steps
        if self.run_on_vm:
            self.vm.addDownloadGitDir(repo_url = repo_url,
                                    dest_dir = dest_dir,
                                    mode = mode,
                                    use_new = use_new,
                                    steps = this_step)
        else:
            # the Try module does not work with the new Git module 0.8.5
            if use_new:
                self.factory.addStep(Git(repourl=repo_url, mode='full', method='clean'))
            else:
                self.factory.addStep(GitOld(repourl=repo_url, mode=mode))
            iter_dir = False
            last = len(this_step)
            cmpt = 1
            for step in this_step:
                final_dst = '/tmp'+ dest_dir
                if cmpt == last:
                    final_dst = dest_dir
                if not iter_dir:
                    iter_dir = step.addDownloadDirectory('../build', final_dst)
                else:
                    iter_dir = step.addDownloadDirectory(iter_dir, final_dst)
                cmpt += 1

    def addMakeDirectory(self, directory):
        self.factory.addStep(ShellCommand(
            command = self.commands.basic('mkdir','-p', directory),
            description = 'Creating ' + directory,
            descriptionDone = directory,))

    def addCpDirectory(self, src_dir, dst_dir):
        self.factory.addStep(ShellCommand(
            command = self.commands.basic(['bash', '-c', ' '.join(['rm','-rf', dst_dir, '&&',
                           'mkdir', '-p', dst_dir, '&&', 
                           'cp', '-a',src_dir + '/*', dst_dir])]),
            description = 'Copying Dir',
            descriptionDone = 'Dir Copied'))

    def addCpFile(self, src_file, dst_file):
        dst_dir = os.path.dirname(dst_file)
        self.factory.addStep(ShellCommand(
            command = self.commands.basic(['bash', '-c', ' '.join(
                            ['mkdir', '-p', dst_dir, '&&',
                             'cp', '-f', src_file, dst_file])]),
            description = 'Copying file',
            descriptionDone = 'File copied'))

    def addSetProperty(self, command = [], description = 'Setting Property', **kwargs):
        self.factory.addStep(shell.SetProperty(
                command=self.commands.simple(command),
                description = description,
                **kwargs))

    def addSetPropertyTF(self, command = [], description = 'Setting Property', **kwargs):
        cmd = self.commands.simple(['bash', '-c',' '.join(command + [' && echo TRUE'])])
        cmd[-1] += ' || echo FALSE'
        
        self.factory.addStep(shell.SetProperty(
                command = cmd,
                description = description,
                **kwargs))

    def addShellCmd(self, command=[], workdir = None, **kwargs):
        cmd = self.commands.simple(cmd = command, workdir = workdir)
        self.addShellCmdBasic(command = cmd,
                             **kwargs)

    def addShellCmdBasic(self, command=[], description = 'Running', descriptionDone='Done',
                        timeout=1200, doStepIf=True, **kwargs):
        self.factory.addStep(ShellCommand(
                command = command,
                description = description,
                descriptionDone = descriptionDone,
                timeout = timeout,
                doStepIf = doStepIf,
                **kwargs
                ))

    def addCommandIf(self, command = [], true_or_false = 'FALSE',
                    property_name = '', doStepIf = False, **kwargs):
        description = 'Running Maybe'
        descriptionDone = 'Done Maybe'
        if 'description' in kwargs:
            description = kwargs['description']
        if 'descriptionDone' in kwargs:
            descriptionDone = kwargs['descriptionDone']
        doStepIf = lambda s, name=property_name,tf=true_or_false: \
            s.getProperty(name,'FALSE') == tf
        print "DOING TOTOT: " + ' '.join(command)
        self.factory.addStep(ShellCommand(
                command = self.commands.simple(command),
                doStepIf = doStepIf,
                **kwargs
                ))

