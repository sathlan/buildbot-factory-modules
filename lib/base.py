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
from buildbot.process.factory import BuildFactory
from buildbot.config import BuilderConfig
from buildbot.schedulers.trysched import Try_Userpass

import re
import tempfile
import os.path
from inspect import isfunction
import copy

class BuilderWithQuick():
    """
    Helper class which create two factories : one with the install
    steps, one without name X{<name>_test}.  Syntaxic sugar really.
    """
    def __init__(self, 
                 builder = None, name = 'runtests', runners = [], steps = [], try_s = [], **kwargs):
        self.builder = builder
        self.name    = name
        self.runners = runners
        self.steps   = steps

        self.factories = {
            name            : BuildFactory(),
            name + '_quick' : BuildFactory()}

        for runner in self.runners:
            for factory_name, factory in self.factories.iteritems():
                runner.factory = factory
                for father in runner.get_father():
                    father.factory = factory
                m = re.search('quick', factory_name)
                if m:
                    runner.start(quick = True)
                else:
                    runner.start(quick = False)
    
                self.builder.append(
                    BuilderConfig(name    = factory_name,
                                  factory = factory,
                                  **kwargs))
            if try_s:
                try_s[0].append(Try_Userpass(
                        name='try',
                        builderNames=self.factories.keys(),
                        port=try_s[1],
                        userpass=[('sampleuser','samplepass')]))

    def __getattr__(self, name):
        """
        Dispatcher to catchall function.
        """
        self.__func = name
        return getattr(self, 'catchall')

    def catchall(self, *args, **kwargs):
        """
        Send function to the runner class.
        """
        for runner in self.runners:
            for factory_name, factory in self.factories.iteritems():
                runner.factory = factory
                for father in runner.get_father():
                    father.factory = factory
                getattr(runner, self.__func)(*args, **kwargs)

class Base(object):
    """
    Define all helper necessary functions.  This class must be
    inherited by all modules.  If the class is to be a virtual
    machine, L{Vm} should be inherited instead.
    """
    def __init__(self, vm = None, factory = ''):
        self._factory = factory

        if vm != None:
            self.run_on_vm = True
        else:
            self.run_on_vm = False
        self.vm          = vm
        self.is_vm       = False
        self.can_snap    = False
        self.post_start_hook = []
        self.pre_start_hook  = []
        self.fathers         = []
        self.from_inside     = False
        try:
            self.name
        except AttributeError:
            self.name = 'Unknown'

        for father in self.get_father():
            father.fathers += self.fathers + [self]

    def set_factory(self, factory):
        self._factory = factory

    def get_factory(self):
        return self._factory

    factory = property(fget = get_factory, fset = set_factory)

    def get_father(self):
        """
        Iterator that return each parent vm to the caller.
        """
        father = self
        while father.run_on_vm:
            father = father.vm
            yield father

    def _start(self, from_inside = True, **kwargs):
        """
        Helper method which enforce that starts is call only by the
        last element in the chain.
        """
        self.from_inside = from_inside
        return self.start(**kwargs)

    def start(self, first = True, quick = False):
        """
        This is the heart of the program.  It creates the precise
        sequence of step which enable:
        1. to start the underlying vm(s) if necessary;
        2. to install necessary paquages;
        3. to take the snapshot at the end of the setup if the underlying vm permit it.
        """

        #: This will be the vm (if available) that will take the snap at the end.
        snapper = None

        if self.run_on_vm:
            # recurse
            snapper = self.vm._start(quick = quick, first = False)

        if len(self.fathers) > 0 and not self.from_inside:
            # The user call a underlying vm directly.  Forbid it.
            father = self.fathers[-1].name
            raise MyFactoryError("I must be start from the end of the chain: %s" % father)

        if self.is_vm and self.can_snap and not self.run_on_vm:
            # I the last vm and I can snap, so I'm the snapper.
            snapper = self

        if snapper:
            # got a snapper
            if first and not quick:
                # I'm in the first level caller and I'm not in a hury.
                snapper.addSetPropertyTF(
                    command = snapper.commands.snap_exists(self.name),
                    property = self.name)

        for command in self.pre_start_hook:
            command()

        if not quick:
            self.install_packages()
            if self.is_vm:
                self.install_vm()
    
            if self.can_snap:
                self.install_snap()
    
            if self.is_vm:
                self.start_vm()

            for command in self.post_start_hook:
                command()

        if first and snapper:
            # If I'm the caller (last step) and I've got a snapper, so
            # revert to it.
            snapper.addRevertToSnap(self.name, assume_exists = True)

        if not quick and snapper:
            # Take the snap if necessary at the end of the setup
            snapper.addTakeSnap(self.name)

        return snapper

    def with_bash(self, cmd = []):
        return ['bash', '-c', ' '.join(cmd)]

    def addStep(self, step):
        """ Delegator to the buildbot factory module. """
        self.factory.addStep(step)

    def addDownloadFile(self, src_file, dst_file, workdir = '/', as_root = False):
        """ 
        Download a nfile from the master to the slave.

        It will properly handle the copy to all the underlying vm.
        """
        self._addDownloadFile(src_file, dst_file, workdir, as_root)

    def _addDownloadFile(self, src_file, dst_file, workdir = '/', as_root = False,
                         steps = [], nbr_steps = 0):
        """ This is where the real meat is.  Recurse all the way back
        to the root vm and depile the stack of intermediary vm asking
        them to upload the file to its final destination.

        The actual Downloading from one vm to another is delegated to
        each vm class with the L{addDownloadFileFromSocle} method.
        """
        this_step = [self] + steps
        if self.is_vm:
            nbr_steps += 1
        if self.run_on_vm:
            self.vm._addDownloadFile(src_file = src_file,
                                     dst_file = dst_file,
                                     workdir  = workdir,
                                     steps    = this_step,
                                     nbr_steps = nbr_steps,
                                     as_root   = as_root)
        else:
            # "root" vm
            last = len(this_step)
            dst_file_rel = dst_file
            workdir_rel  = workdir
            if os.path.isabs(workdir):
                workdir_rel = os.path.relpath(workdir,'/')
            if os.path.isabs(dst_file):
                dst_file_rel = os.path.relpath(dst_file,'/')
            # workdir and all are for the final vm, here we assure
            # that the final file will be in 'build/<workdir>/<dst_file>
            dst_file_rel = os.path.join(workdir_rel, dst_file_rel)
            # when only one step the hardware node is the final destination.
#            if last == 1:
#                dst_file_rel = os.path.join('/', dst_file_rel)
            if not os.path.exists(src_file):
                self.addStep(StringDownload(s         = src_file,
                                            slavedest = dst_file_rel))
            else:
                self.addStep(FileDownload(mastersrc = src_file,
                                          slavedest = dst_file_rel))
            # now I deleguate the "upload" to each vm.
            iter_file = False
            cmpt = 1
            for step in this_step:
                if not step.is_vm: # only work with vm
                    cmpt += 1
                    continue
                dest_dir_tmp = dst_file
                if os.path.isabs(dst_file):
                    dst_file_tmp =  os.path.relpath(dst_file,'/')
                final_dst = os.path.join('/tmp', dst_file_tmp)
                # final destination
                as_root_final = False
                if cmpt == nbr_steps:
                    final_dst = dst_file
                    as_root_final = as_root
                if not iter_file: # root vm
                    iter_file = step.addDownloadFileFromSocle(
                        src_file = dst_file_rel, 
                        dst_file = final_dst, 
                        workdir  = workdir,
                        as_root  = as_root_final)
                else:           # itermediary vm
                    iter_file = step.addDownloadFileFromSocle(
                        src_file = iter_file, 
                        dst_file = final_dst, 
                        workdir  = workdir,
                        as_root  = as_root_final)
                cmpt += 1

    def addDownloadGitDir(self, repo_url = '', dest_dir = '', mode='copy',
                          use_new = False, as_root = False):
        """ Download a dir a Git(+patch) repository.  Support any number of underlying VM """
        self._addDownloadGitDir(repo_url, dest_dir, mode, use_new, as_root)

    def _addDownloadGitDir(self, repo_url = '', dest_dir = '', mode='copy', use_new = False,
                           as_root = False, steps = [], nbr_steps = 0):
        this_step = [self] + steps
        if self.is_vm:
            nbr_steps += 1
        if self.run_on_vm:
            self.vm._addDownloadGitDir(repo_url  = repo_url,
                                       dest_dir  = dest_dir,
                                       mode      = mode,
                                       use_new   = use_new,
                                       steps     = this_step,
                                       nbr_steps = nbr_steps,
                                       as_root   = as_root)
        else:
            # the Try module does not work with the new Git module 0.8.5
            if use_new:
                self.addStep(Git(repourl=repo_url, mode='full', method='clean'))
            else:
                self.addStep(GitOld(repourl=repo_url, mode=mode))
            iter_dir = False
            cmpt = 1
            for step in this_step:
                if not step.is_vm:
                    cmpt += 1
                    continue
                dest_dir_tmp = dest_dir
                if os.path.isabs(dest_dir):
                    dest_dir_tmp =  os.path.relpath(dest_dir,'/')
                final_dst = os.path.join('/tmp', dest_dir_tmp)
                if cmpt == nbr_steps: # != of last, it's the nbr_of_ VM steps
                    final_dst = dest_dir
                if not iter_dir:
                    iter_dir = step.addDownloadDirectory('../build', final_dst, as_root)
                else:
                    iter_dir = step.addDownloadDirectory(iter_dir, final_dst, as_root)
                cmpt += 1

    def addMakeDirectory(self, directory, as_root = False, **kwargs):
        self.addStep(ShellCommand(
            command = self.commands.simple('mkdir','-p', directory),
            description = 'Creating ' + directory,
            haltOnFailure = True,
            descriptionDone = directory,
            **kwargs))

    def addCpDirectory(self, src_dir, dst_dir, as_root = False, **kwargs):
        """ Copy a directory, ensure it's pristine new each time.  """
        cmd = ['bash', '-c', ' '.join(['rm','-rf', dst_dir, '&&',
                                       'mkdir', '-p', dst_dir, '&&', 
                                       'cp', '-af',src_dir + '/*', dst_dir])]
        if as_root:
            cmd = ['sudo'] + cmd
        self.addStep(ShellCommand(
            command = self.commands.simple(cmd),
            haltOnFailure = True,
            description = 'Copying Dir',
            descriptionDone = 'Dir Copied',
            **kwargs))

    def addCpFile(self, src_file, dst_file, as_root = False, **kwargs):
        dst_dir = os.path.dirname(dst_file)
        cmd = ['bash', '-c', ' '.join(
                ['mkdir', '-p', dst_dir, '&&',
                 'cp', '-vf', src_file, dst_file])]
        if as_root:
            cmd = ['sudo'] + cmd
        self.addStep(ShellCommand(
                haltOnFailure = True,
                command = self.commands.simple(cmd),
                description = 'Copying file',
                descriptionDone = 'File copied',
                **kwargs))

    def addSetProperty(self, command = [], description = 'Setting Property', **kwargs):
        self.addStep(shell.SetProperty(
                command=self.commands.simple(command),
                description = description,
                **kwargs))

    def addSetPropertyTF(self, command = [], 
                         description = 'Setting Property',
                         descriptionDone = False,
                         property = '',
                         **kwargs):
        """ 
        Convenient method to set a property to TRUE or FALSE depending
        on the status of a shell command
        """
        if not descriptionDone:
            descriptionDone = property

        cmd = self.commands.simple(['bash', '-c',' '.join(command + [' && echo TRUE'])])
        cmd[-1] += ' || echo FALSE'
        
        self.addStep(shell.SetProperty(
                command = cmd,
                description = description,
                descriptionDone = descriptionDone,
                property = property,
                **kwargs))

    def addShellCmd(self, command=[], workdir = None, **kwargs):
        """
        Main method to add a shell command.  It will properly handle
        the underlying vm and execute the code in the final one.

        It delegates the command creation (which handle the underlying
        vm) to the X{simple} methode of the X{<User>Command} module
        provided.
        """
        cmd = self.commands.simple(cmd = command, workdir = workdir)
        self.addShellCmdBasic(command = cmd,
                             **kwargs)

    def addShellCmdBasic(self, command=[], description = 'Running', descriptionDone='Done',
                        timeout=1200, doStepIf=True, **kwargs):
        """
        The same as L{addShellCmd} but use the X{basic} method which
        should not any decoration to the command, but the underlying
        vm handle code.
        """
        self.addStep(ShellCommand(
                haltOnFailure = True,
                command = command,
                description = description,
                descriptionDone = descriptionDone,
                timeout = timeout,
                doStepIf = doStepIf,
                **kwargs
                ))

    def addCommandIf(self, command = [], **kwargs):
        self.addCommandIfRaw(command = self.commands.simple(command), **kwargs)

    def addCommandIfBasic(self, command = [], **kwargs):
        self.addCommandIfRaw(command = self.commands.basic(command), **kwargs)

    def addCommandIfRaw(self, command = [], true_or_false = 'FALSE',
                        property_name = '', doStepIf = False, assume = 'FALSE', **kwargs):
        """
        Add a step if a certain X{Property} is met.

        Designed to work with L{addSetPropertyTF}.  It can be
        configured to assume TRUE or FALSE if the property is missing.
        It will test against TRUE or FALSE as required.

        By default, assumes FALSE and do the command only if FALSE.
        """
        description = 'Running Maybe'
        descriptionDone = 'Done Maybe'
        if 'description' in kwargs:
            description = kwargs['description']
        if 'descriptionDone' in kwargs:
            descriptionDone = kwargs['descriptionDone']
        # this is the test
        doStepIf = lambda s, name=property_name,tf=true_or_false: \
            s.getProperty(name, assume) == tf
        self.addStep(ShellCommand(
                haltOnFailure = True,
                command       = command,
                doStepIf      = doStepIf,
                **kwargs))

    def add_to_post_start_hook(self, step):
        """ Hook to enable caller to stuck steps before the installation. """
        self.post_start_hook.append(step)
        

    def add_to_pre_start_hook(self, function):
        """ Hook to enable caller to stuck steps after the installation. """
        self.pre_start_hook.append(function)
