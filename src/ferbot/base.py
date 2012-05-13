# Try schedule does not work with the new git module
# -*- coding: UTF-8 -*-
# version 0.8.5 12/21/04
from error import MyFactoryError
from my_builders import ThisBuilder
from my_commands import Dummy

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
from buildbot.changes.filter import ChangeFilter

class OneFactory(object):
    """
    Represent a tree of builder.
    """

    def __init__(self, root):
        self.root = root
        self.children = []

    def add(self, child):
        self.children += [child]

class MyName(object):
    _instance = None
    _names    = set([])
    def __new__(laClasse, *args, **kwargs): 
        "méthode de construction standard en Python"
        if laClasse._instance is None:
            laClasse._instance = object.__new__(laClasse, *args, **kwargs)
        return laClasse._instance

    def uniq(self, name):
        suffix = ""
        uniq   = name
        # TODO: should lock somewhere
        cpt    = 0
        while uniq in MyName._names:
            suffix = "-%d" % cpt
            cpt += 1
            uniq = name + suffix
        MyName._names.add(uniq)
        return uniq

class BuilderFactory(object):
    """
    Singleton class that hold all the definition made by the user.

    Then we can make sure that the longest path is used by the user.

    TODO: It works on tree not forest.
    """
    # http://fr.wikipedia.org/wiki/Singleton_(patron_de_conception)#Python
    _instance  = None       # Attribut statique de classe
    _has_started = False
    _callers   = []
    _trees_bag = []
    _builders  = []
    def __new__(laClasse, *args, **kwargs): 
        "méthode de construction standard en Python"
        if laClasse._instance is None:
            laClasse._instance = object.__new__(laClasse, *args, **kwargs)
        return laClasse._instance

    def __init__(self, caller):
        BuilderFactory._callers += [caller]
        self.callers     = BuilderFactory._callers
        self.max         = caller
        self.builders    = BuilderFactory._builders
        self.__func      = ''

    def add_builder(self, builder):
        BuilderFactory._builders.append(builder)
        self.builders = BuilderFactory._builders

    def is_root(self, builder):
        
        if builder.root in self.roots():
            return True
        else:
            return False

    def get_builders(self):
        for builder in BuilderFactory._builders:
            yield builder

    def get_root_builders(self):
        for root in self.get_builders():
            if self.is_root(root):
                yield root

    def has_started(self):
        started = BuilderFactory._has_started
        BuilderFactory._has_started = True
        return started

    def max(self):
        maybe = self.max
        for caller in self.callers:
            if caller.max_descendant_depth > maybe.max_descendant_depth:
                maybe = caller
        self.max = maybe

    def roots(self):
        roots = set([])
        with_parent = set([])
        print "The caller of %s are %s" % (self, self._callers)
        for caller in self._callers:
            for path in caller.paths:
                print "	DESCENDANTS of %s are %s" % (caller, path)
                if set(path[:-1]) or len(path) == 1:
                    # we don't want union with empty set
                    with_parent |= set(path[:-1])
                    roots.add(path[-1])
                    print "		Adding %s as root" % path[-1]
                roots -= with_parent
        return roots

    def get_builders_name(self):
        names = []
        for builder in self.get_builders():
            names.append(builder.get_builder_name())
        return names

    def get_builders_name_quick(self):
        names = []
        for builder in self.builders:
            if builder.quick:
                names.append(builder.get_builder_name())
        return names
        
    def addBuilder(self, builders = [], **kwargs):
        print "ADDING BUILDER"
        for builder in self.get_root_builders():
            name    = builder.get_builder_name()
            factory = builder.get_factory()
            print "	DEBUG : CREATING BUILDER %s (%s)" % (name, self.roots())
            builders.append(
                BuilderConfig(name    = name,
                              factory = factory,
                              **kwargs))

    def __getattr__(self, name):
        """
        Dispatcher to catchall function.
        """
        self.__func = name
        return getattr(self, 'dispatch')

    def dispatch(self, *args, **kwargs):
        to = None
        if kwargs.has_key('to'):
            to = kwargs['to']
            del kwargs['to']
        for builder in self.builders:
            builder.update_vm()
            builder.update_factory()
            destination = builder.root
            if to:
                destination = to
            print "BUILDER %s and ROOT %s and func %s (%s)" % (builder, destination, self.__func, to)
            getattr(destination, self.__func)(*args,**kwargs)

class Base(object):
    """
    Define all helper necessary functions.  This class must be
    inherited by all modules.  If the class is to be a virtual
    machine, L{Vm} should be inherited instead.
    """
    def __init__(self, vm = None, vms = [], factory = ''):
        self._factory = factory

        if vm != None or vms != []:
            self.run_on_vm = True
        else:
            self.run_on_vm = False
        #: the vm on which the steps take place
        self.vm          = vm
        #: multiple vm can be specified instead.
        #: if a list, then a list of factories will be returned by L{start}
        #: if a dict, then it's L{'vm1' : [ vm_obj, factory_obj], ...}
        self.is_vm       = False
        self.can_snap    = False
        self.commands    = Dummy(self.name)
        self.paths       = []
        self.post_start_hook = []
        self.pre_start_hook  = []
        self.fathers         = []
        self.from_inside     = False
        self.parents         = []
        #: keep track of the whole path that led here
        self.ancestors       = []
        #: keep track of all the final leave from here
        self.descendants     = set([])
        self.vms             = vms
        self.builderfactory    = BuilderFactory(self)
        #: just a counter for statistics
        self.nbr_of_steps    = 0
        try:
            self.name
        except AttributeError:
            self.name = 'Unknown'
        # fill ancestors and descendants
        self._get_parent()
        # and some stats
        self.max_descendant_depth = 0
        for descendant in self.descendants:
            depth = len(descendant.ancestors)
            if self.max_descendant_depth < depth:
                self.max_descendant_depth = depth

        # debug inforamtion
        print ">>> DESCENDANTS OF %s (%s)" % (self ,self.name)
        for d in self.descendants:
            print "	%s (%s)" % (str(d), d.name)
            print "		with ancestors %s (%s)" % \
                (str(d.paths), str(map(lambda x:zip(x), d.paths)))
        print "<<< DESCENDANTS OF %s (%s)" % (self ,self.name)

    def _get_parent(self):
        """
        DSF of the ancestors giving back the complete path to the caller.
        """
        parent = self
        ancestors = []
        # fill the number of children that will have this element as an ancestor
        for cpt in self.vms:
            ancestors = [self] + ancestors
        # tricky!  Make a copy of parent.vms instead of keeping a
        # pointer on it, to avoid modification when we pop it.
        children = [] + parent.vms
        # depth first traversal
        while children:
            parent = children.pop()
            children += parent.vms
            # get its ancestor
            direct_ancestor = ancestors.pop()
            # record the path to the root
            parent.ancestors = [direct_ancestor] + direct_ancestor.ancestors
            # fill the number of children that will have this element as an ancestor
            for cpt in parent.vms:
                ancestors = [parent] + ancestors
            if not parent.vms:
                # record the end of a path
                if parent in self.descendants:
                    raise MyFactoryError(
                        "We got a cycle in the tree of dependances! %s appears twice." % \
                            parent.name)
                self.descendants.add(parent)
        for cpt, descendant in enumerate(self.descendants):
            self.paths.append([descendant] + descendant.ancestors)
        if len(self.paths) == 0:
            self.paths = [[self]]
        print "MY PATH IS: (%s)" % self
        print "	%s " % self.paths
            
    def set_factory(self, factory):
        self._factory = factory

    def get_factory(self):
        return self._factory

    factory = property(fget = get_factory, fset = set_factory)

    def start(self):
        """
        This is the heart of the program.  It creates the precise
        sequence of steps which enable:
        1. to start the underlying vm(s) if necessary;
        2. to install necessary paquages;
        3. to take the snapshot at the end of the setup if the underlying vm permit it.

        The steps are added to the factory by L{addStep}.

        It B{HAS TO BE} started from the last element in the chain,
        not a sub-vm.

        It supports several root elements.

        When called, it returns the factories to the user, who can
        then add steps to each.  The factories is a hash of root
        composed of a hash of names/factory elements.
        """
        # TODO: should return a object to facilitate adding step:
        # check puppet/master.cfg
        print ">>> ROOTS:"
        for root in self.builderfactory.roots():
            print "	 roots are %s (%s)" % (root, root.name)
        print "<<< ROOTS:"

        if self.builderfactory.has_started():
            raise MyFactoryError("Start has to be called only one time.")

        if self not in self.builderfactory.roots():
            raise MyFactoryError("Must be called from the last element in the chain \"%s\"not %s" \
                                     % ('or '.join(
                        map(lambda x: x.name + ' ', self.builderfactory.roots())), 
                                        self.name))
        # We are good to go.
        factories    = {}
        nbr_of_chains   = 0
        nbr_of_elements = 0
        nbr_of_steps    = 0
        
        for quick in [False, True]:
            for root in self.builderfactory.roots():
                
                print 'ROOT: %s (%s)' % (root, str(quick))
                root_name = root.name
                if quick:
                    root_name += '_quick'
                # TODO: support multi-vms definitions
                print "STARTING FROM %s" % root
                for one_path in root.paths:
                    b = ThisBuilder(root = root, path = one_path, quick = quick)
                    self.builderfactory.add_builder(b)
    
                    path = b.get_path()
                    current_factory_name = b.get_factory_name()
    
                    current_factory = b.get_factory()
    
                    b.update_vm()
                    b.update_factory()
                    # now we can start, and the behaviour will be ok.
                    snapper = None
                    if path[0].can_snap:
                        snapper = path[0]
    
                    if not quick and snapper:
                        snapper.addSetPropertyTF(
                            command = snapper.commands.snap_exists(root.name),
                            property = root.name)
                    nbr_of_chains += 1
                    level = 1
                    last  = len(path)
                    for element in path:
                        print "	ELEMENT: %s" % element.name
                        nbr_of_elements += 1
                        for command in element.pre_start_hook:
                            command()
            
                        if not quick:
                            # TODO: should install heavy, non changing
                            # stuff.  All those commands should be
                            # idempotent, ie, doing it over an
                            # existing installation should work
                            # (better still, it shld avoid to install
                            # them again altogther with a embeded
                            # test.)
                            element.install_packages()
                            if element.is_vm:
                                element.install_vm()
                
                            if element.can_snap and level == 0:
                                element.install_snap()
                
                            if element.is_vm:
                                element.start_vm()
            
                            # should install lightweight stuff and a
                            # snap should be done before this one.
                            # Then we can delete the last snap without
                            # having to reinstall the heavy stuff
                            # again.
                            for command in element.post_start_hook:
                                command()
    
                        if level == last and snapper:
                            # If I'm the caller (last step) and I've got a snapper, so
                            # revert to it.
                            print "DEBUG: REVERTING TO %s for %s" % (element.name, element)
                            snapper.addRevertToSnap(element.name, assume_exists = True)
    
                        if not quick and snapper:
                            # Take the snap if necessary at the end of the setup
                            snapper.addTakeSnap(element.name)
    
                        # stats
                        if snapper != element:
                            nbr_of_steps += element.nbr_of_steps
                            element.nbr_of_steps = 0
                        level += 1
                if snapper:
                    nbr_of_steps += snapper.nbr_of_steps
                    snapper.nbr_of_steps = 0
        print "CREATED %d chains with %d elements composed of %d steps" % \
            (nbr_of_chains, nbr_of_elements, nbr_of_steps)
        import pprint
        pp = pprint.PrettyPrinter()
        pp.pprint(factories)
        return self.builderfactory

#        #: This will be the vm (if available) that will take the snap at the end.
#        snapper = None
#
#        if self.run_on_vm:
#            # recurse
#            snapper = self.vm._start(quick = quick, first = False)
#
#        if len(self.fathers) > 0 and not self.from_inside:
#            # The user call a underlying vm directly.  Forbid it.
#            father = self.fathers[-1].name
#            raise MyFactoryError("I must be start from the end of the chain: %s" % father)
#
#        if self.is_vm and self.can_snap and not self.run_on_vm:
#            # I the last vm and I can snap, so I'm the snapper.
#            snapper = self
#
#        if snapper:
#            # got a snapper
#            if first and not quick:
#                # I'm in the first level caller and I'm not in a hury.
#                snapper.addSetPropertyTF(
#                    command = snapper.commands.snap_exists(self.name),
#                    property = self.name)
#
#        for command in self.pre_start_hook:
#            command()
#
#        if not quick:
#            self.install_packages()
#            if self.is_vm:
#                self.install_vm()
#    
#            if self.can_snap:
#                self.install_snap()
#    
#            if self.is_vm:
#                self.start_vm()
#
#            for command in self.post_start_hook:
#                command()
#
#        if first and snapper:
#            # If I'm the caller (last step) and I've got a snapper, so
#            # revert to it.
#            snapper.addRevertToSnap(self.name, assume_exists = True)
#
#        if not quick and snapper:
#            # Take the snap if necessary at the end of the setup
#            snapper.addTakeSnap(self.name)
#
#        return snapper

    def addStep(self, step):
        """ 
        Delegator to the buildbot factory module.

        All sub-class should use this X{addStep} and not
        X{self.factory.addStep} directly.
        """

        self.nbr_of_steps += 1
        print "		STEP: %s (%s)" % (step, self.factory)
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
                          use_new = False, as_root = False, **kwargs):
        """ Download a dir a Git(+patch) repository.  Support any number of underlying VM """
        self._addDownloadGitDir(repo_url, dest_dir, mode, use_new, as_root, **kwargs)


    def _addDownloadGitDir(self, repo_url = '', dest_dir = '', mode='copy', use_new = False,
                           as_root = False, steps = [], nbr_steps = 0, **kwargs):
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
                                       as_root   = as_root,
                                       **kwargs)
        else:
            # the Try module does not work with the new Git module 0.8.5
            if use_new:
                self.addStep(Git(repourl=repo_url,
                                 mode='full',
                                 method='clean',
                                 **kwargs))
            else:
                self.addStep(GitOld(repourl=repo_url, 
                                    mode=mode,
                                    **kwargs))
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
