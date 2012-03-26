# -*- python -*-
# ex: set syntax=python:

from os import *
from buildbot.steps import shell
from buildbot.process.properties import Property
from buildbot.steps.shell import ShellCommand
from buildbot.steps.source.git import Git

class VagrantCmds:
    def __init__(self, machine = ''):
        self.machine = machine
        print 'GOT MACHINE: ' + self.machine + ':'

    def ssh(self, cmd=[]):
        command = ['vagrant', 'ssh']
        if self.machine:
            command += [ self.machine ]
        command += [ '-c' ]
        return command + [' '.join(cmd)]

    def snap(self, command = '', snap=''):
        cmd = ['vagrant', 'snap', command]
        if command == 'take':
            if self.machine:
                cmd += [ self.machine ]
            cmd += ['-n',snap, '-d', 'Done by Buildbot.']
        elif command == 'list':
            if self.machine:
                cmd += [ self.machine ]
        else:
            cmd += [snap]
            if self.machine:
                cmd += [ self.machine ]
        return cmd
        
    def up(self):
        cmd = ['vagrant', 'up']
        if self.machine:
            cmd += [ self.machine ]
        return cmd

    def init(self, boxname, boxurl):
        cmd = ['vagrant', 'init', boxname, boxurl]
        return cmd

    def snap_exists(self, snap = ''):
        cmd = self.__make_vagrant_output_test(['snap', 'list'], snap)
        return cmd

    def vm_is_running(self):
        cmd = self.__make_vagrant_output_test(['status'], 'running')
        return cmd

    def __make_vagrant_output_test(self, cmd = [], grep= '_does_not_existssss'):
        command = [ 'vagrant' ] + cmd
        if self.machine:
            command += [ self.machine ]
        str_cmd = '( ' + ' '.join(command) + ' 2>/dev/null | egrep -q \'' +\
            grep + '\' && echo TRUE ) || echo FALSE'
        return [ 'bash', '-c', str_cmd ]
        
class Vagrant:
    def __init__(self, factory='',basedir='', machine='', vagrantfile_source='',vagrantfile='Vagrantfile', boxname='', boxurl='',want_init_snap_named='initial_state'):
        self.factory=factory
        self.basedir=basedir
        self.machine=machine
        self.vagrantfile_source=vagrantfile_source
        self.vagrantfile=path.join(self.basedir, vagrantfile)
        self.boxname=boxname
        self.boxurl= boxurl
        self.want_init_snap_named=want_init_snap_named
        self.vagrant_cmd = VagrantCmds(machine)

        self.factory.addStep(shell.SetProperty(
                command='([ -e ' + self.vagrantfile + ' ] && echo TRUE) || echo FALSE',
                description='Setting property',
                property='vagrant_is_installed'))
        self._init_vagrant()

    def addShellCmd(self, cmd=[], running = 'Running', done='Done', timeout=1200, dostep=True):
        command = self.vagrant_cmd.ssh(cmd)
        self.factory.addStep(ShellCommand(
                command = command,
                description = running,
                descriptionDone = done,
                timeout = timeout,
                workdir = self.basedir,
                doStepIf = dostep,
                ))

    def addRevertToSnap(self, snap_name='initial_state'):
        cmd = self.vagrant_cmd.snap('go',snap_name)
        self.doCommandIf(cmd = cmd,
                         true_or_false = 'TRUE',
                         description = 'Reverting',
                         descriptionDone = 'Revert to ' + snap_name,
                         property_name = snap_name)

    def doCommandIf(self, cmd = [], true_or_false = 'FALSE',
                    property_name = '', **kwargs):

        description = 'Running Maybe'
        descriptionDone = 'Done Maybe'
        if 'description' in kwargs:
            description = kwargs['description']
        if 'descriptionDone' in kwargs:
            descriptionDone = kwargs['descriptionDone']
        check = lambda s, name=property_name,tf=true_or_false: \
            s.getProperty(name,'FALSE') == tf
        self.factory.addStep(ShellCommand(
                command = cmd,
                description = description,
                descriptionDone = descriptionDone,
                doStepIf = check,
                workdir = self.basedir))
        
        
    def addTakeSnap(self, snap_name='____non_exististing_snap'):
        self.doCommandIf(cmd = self.vagrant_cmd.snap('take', snap_name),
                         true_or_false = 'FALSE',
                         property_name = snap_name,
                         description = 'Snapping',
                         descriptionDone = 'Snapped')

    def goto_or_take_snap(self, snap):
        self.factory.addStep(shell.SetProperty(
                command=self.vagrant_cmd.snap_exists(snap),
                workdir=self.basedir,
                description='Setting property',
                property=snap))
        self.addTakeSnap(snap)
        self.addRevertToSnap(snap)
        
    def _init_vagrant(self):
        self.factory.addStep(ShellCommand(
                command = ['mkdir', '-p', self.basedir],
                description = 'Creating base dir',
                descriptionDone = 'Dir created',
                doStepIf = lambda s: s.getProperty('vagrant_is_installed') == 'FALSE'))
        self.factory.addStep(shell.SetProperty(
                command=self.vagrant_cmd.vm_is_running(),
                workdir=self.basedir,
                description='Setting property',
                property='machine_is_running'))
        if self.vagrantfile_source:
            # if the '.vagrant' file is not in the .gitignore it will
            # be deleted, so it must be added (manually)
            self.factory.addStep(Git(repourl=self.vagrantfile_source,
                                     mode='full',
                                     method='clean',
                                     description='Checking out Vagrant',
                                     descriptionDone='Vagrant checked out',
                                     workdir = self.basedir))
        elif self.boxname and self.boxurl:
            self.factory.addStep(ShellCommand(
                    description='Initializing Vagrant',
                    descriptionDone='Vagrant initialized',
                    workdir = self.basedir,
                    doStepIf = lambda s: s.getProperty('vagrant_is_installed') == 'FALSE',
                    command = self.vagrant_cmd.init(self.boxname,self.boxurl)))

        cmd = self.vagrant_cmd.up()
        self.factory.addStep(ShellCommand(
                description='Starting VBox',
                descriptionDone='VBox up',
                command = cmd,
                doStepIf = lambda s: s.getProperty('machine_is_running') == 'FALSE',
                workdir = self.basedir,))

        if self.want_init_snap_named:
            self.goto_or_take_snap(self.want_init_snap_named)
