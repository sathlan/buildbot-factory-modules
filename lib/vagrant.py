# -*- python -*-
# ex: set syntax=python:

from os import *
import os.path
import string

from vm   import Vm

from my_commands import Commands

from buildbot.steps import shell
from buildbot.process.properties import Property
from buildbot.steps.shell import ShellCommand
# Try schedule does not work with the new git module
# version 0.8.5 12/21/04
from buildbot.steps.source import Git as GitOld
# the new version offers more choice for git, like keeping file from
# gitignore.
from buildbot.steps.source.git import Git
from buildbot.steps.transfer import StringDownload

from buildbot.process.properties import WithProperties

VAGRANT_VERSION='1.0.2'
VAGRANT_SNAP_VERSION='0.10'

class VagrantCmds(Commands):
    def __init__(self, machine = '', basedir = '/', vm = False):
        Commands.__init__(self, vm)
        self.machine = machine
        self.basedir = basedir

    def simple(self, cmd=[]):
        print "DEBUG: SIMPLE -> " + ' '.join(cmd)
        snap_command = False
        if string.find(' '.join(cmd), ' snap ') >= 0:
            snap_command = True
        # snapping inside a VM seems to not work, so we snap the
        # "root" vm.
        if snap_command and self.vm:
            command = self.basic(cmd)       # command_prefix will fill
                                            # in the father prefix
                                            # command
        else:
            command =  self.basic(['bash', '-c', "([ -d '"+self.basedir+"' ] || mkdir -p '"+self.basedir+"') && cd '"+self.basedir+"' && "+' '.join(cmd)])
        return command

    def ssh(self, cmd=[]):
        print "DEBUG: SSH"
        command = ['vagrant', 'ssh']
        if self.machine:
            command += [ self.machine ]
        command += [ '-c' ]
        return self.simple(command + [' '.join(cmd)])

    def snap(self, command = '', snap=''):
        cmd = ['vagrant', 'snap', command]
        if command == 'take':
            if self.machine:
                cmd += [ self.machine ]
            cmd += ['-n',snap, '-d', "'Done by Buildbot.'"]
        elif command == 'list':
            if self.machine:
                cmd += [ self.machine ]
        else:
            cmd += [snap]
            if self.machine:
                cmd += [ self.machine ]
        return self.simple(cmd)
        
    def up(self):
        cmd = ['vagrant', 'up']
        if self.machine:
            cmd += [ self.machine ]
        return self.simple(cmd)

    def init(self, boxname, boxurl = False):
        cmd = ['vagrant', 'init', boxname]
        if boxurl:
            cmd += [boxurl]
        return self.simple(cmd)

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
        return self.simple([ 'bash', '-c', str_cmd ])
        
class Vagrant(Vm):
    def __init__(self, 
                 basedir='', 
                 machine='', 
                 vagrantfile_source='',
                 vagrantfile='Vagrantfile', 
                 boxname='', 
                 boxurl='',
                 fix_network = False,
                 **kwds):

        self.basedir=os.path.expanduser(basedir)
        # MRO should kick in both Vm, and Base, and I should use new style class:
        # http://www.python.org/doc/newstyle/
        Vm.__init__(self, root_vm_dir = self.basedir, commands_class = VagrantCmds, **kwds)
        self.vagrant_cmd = self.commands
        self.machine=machine
        self.vagrantfile_source=vagrantfile_source
        self.vagrantfile=path.join(self.basedir, vagrantfile)
        self.boxname=boxname
        self.boxurl= boxurl
        self.fix_network = fix_network
        if self.want_init_snap_named:
            print 'DEBUG: initial_state is ' + self.want_init_snap_named

    def init_snap(self, name=''):
        self.want_init_snap_named = name

    def add_pre_command(self, commands=[]):
        for cmd in commands:
            self.pre_commands_hook.append(cmd)

    def addShellCmd(self, cmd=[], running = 'Running', done='Done', timeout=1200, dostep=True):
        command = self.vagrant_cmd.ssh(cmd)
        self.factory.addStep(ShellCommand(
                command = command,
                description = running,
                descriptionDone = done,
                timeout = timeout,
                doStepIf = dostep,
                ))

    def start(self):
        property_name = self.want_init_snap_named
        if self.vm:
            self.vm.start()
        self.try_install_virtualbox()
        self.factory.addStep(ShellCommand(
                command=self.vagrant_cmd.simple(
                    ['gem', 'list', '-i vagrant -v', "'"+VAGRANT_VERSION+"'", '||',
                     'sudo', 'gem', 'install vagrant -v', "'"+VAGRANT_VERSION+"'"]),
                description='Installing Vagrant',
                descriptionDone='Vagrant installed',))
        if not self.vm:
            # snapping inside a VM seems to not work and does not make
            # much sense.  We snap at the "root" vm seems to be missing
            # (for snap maybe)
            self.factory.addStep(ShellCommand(
                    command=self.vagrant_cmd.simple(
                        ['gem', 'list', '-i virtualbox', '||',
                         'sudo', 'gem', 'install', 'virtualbox']),
                    description='Installing virtualbox',
                    descriptionDone='Vagrantbox installed',))
            self.factory.addStep(ShellCommand(
                    command=self.vagrant_cmd.simple(
                        ['gem', 'list', '-i vagrant-snap -v', "'"+VAGRANT_SNAP_VERSION+"'", '||',
                         'sudo', 'gem', 'install vagrant-snap -v', "'"+VAGRANT_SNAP_VERSION+"'"]),
                    description='Installing Vagrant Snap',
                    descriptionDone='Vagrant-snap installed',))
                    
        self.factory.addStep(shell.SetProperty(
                command=self.vagrant_cmd.simple(['bash','-c','([ -e ' + self.vagrantfile + ' ] && echo TRUE) || echo FALSE']),
                description='Setting property',
                property='vagrant_is_installed'))

        self.factory.addStep(ShellCommand(
                command = self.vagrant_cmd.simple(['mkdir', '-p', self.basedir]),
                description = 'Creating base dir',
                descriptionDone = 'Dir created',
                doStepIf = lambda s: s.getProperty('vagrant_is_installed') == 'FALSE'))
        self.factory.addStep(shell.SetProperty(
                command=self.vagrant_cmd.vm_is_running(),
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
                                     ))
        elif self.boxname:
            self.factory.addStep(ShellCommand(
                    description='Initializing Vagrant',
                    descriptionDone='Vagrant initialized',
                    doStepIf = lambda s: s.getProperty('vagrant_is_installed') == 'FALSE',
                    command = self.vagrant_cmd.init(self.boxname,self.boxurl)))

        cmd = self.vagrant_cmd.up()
        self.factory.addStep(ShellCommand(
                description='Starting VBox',
                descriptionDone='VBox up',
                command = cmd,
                doStepIf = lambda s: s.getProperty('machine_is_running') == 'FALSE',
                ))
    # used by the next step
        if self.want_init_snap_named:
            self.addTakeSnap('initial_state-vm'+self.make_uniq_initial_name()) # father of all snaps
            self.factory.addStep(shell.SetProperty(
                    command=self.vagrant_cmd.snap_exists(self.want_init_snap_named),
                    description='Setting property',
                    property=self.want_init_snap_named))

        if self.fix_network:
            self.addShellCmd(['sudo', 'dhclient', 'eth0'],running = 'Fixing Net', done = 'Network Fixed')
        # http://www.python.org/dev/peps/pep-0322/
        while self.pre_commands_hook:
            command = self.pre_commands_hook.pop()
            self.addShellCmd(command, running = 'Running Pre-Hook', done='Pre-Hook',
                             dostep = lambda s,n=self.want_init_snap_named: s.getProperty(n, 'FALSE') == 'FALSE')

        if self.want_init_snap_named:
            self.addRevertToSnap(self.want_init_snap_named)
            if self.fix_network:
                self.addShellCmd(['sudo', 'dhclient', 'eth0'],running = 'Fixing Net', done = 'Network Fixed',dostep = lambda s,n=self.want_init_snap_named: s.getProperty(n, 'FALSE') == 'TRUE')

    def addDeleteSnap(self, snap_name='____non_exististing_snap'):
        cmd = self.vagrant_cmd.snap('delete',snap_name)
        self.doCommandIf(cmd = cmd,
                         true_or_false = 'TRUE',
                         description = 'Deleting Snap',
                         descriptionDone = 'Snap Deleted' + snap_name,
                         property_name = snap_name)
        
    def addRevertToSnap(self, snap_name='____non_exististing_snap', assume_exists = False):
        cmd = self.vagrant_cmd.snap('go',snap_name)
        t_or_f = 'TRUE'
        if assume_exists:
            t_or_f = 'FALSE'
        self.doCommandIf(cmd = cmd,
                         true_or_false = t_or_f,
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
                doStepIf = check
                ))
        
        
    def addTakeSnap(self, snap_name='____non_exististing_snap'):
        self.doCommandIf(cmd = self.vagrant_cmd.snap('take', snap_name),
                         true_or_false = 'FALSE',
                         property_name = snap_name,
                         description = 'Snapping',
                         descriptionDone = 'Snapped')
    def addUploadDirectory(self, src_dir, dst_dir):
        """ Must be provided to upload a dir to the vm """
        dir_in_vm = '/upload/'+ dst_dir
        # TODO: make the dir name unique, see next TODO
        tmp_dir = self.basedir + dir_in_vm
        # TODO: WithProperties %(buildername)s-%(buildnumber)s' may work.
        # To upload I just copy to the root vagrant dir as it is shared
        self.addCpDirectory(src_dir + '/', tmp_dir)
        self.factory.addStep(ShellCommand(
                command = self.vagrant_cmd.ssh(['cp','-a', '/vagrant' + dir_in_vm + '/', dst_dir]),
                description = 'Uploading',
                descriptionDone = 'Uploaded'))
        return dst_dir

    def goto_or_take_snap(self, snap):
        self.factory.addStep(shell.SetProperty(
                command=self.vagrant_cmd.snap_exists(snap),
                description='Setting property',
                property=snap))
        self.addTakeSnap(snap)
        self.addRevertToSnap(snap)
        
    def command_prefix(self, cmd = []):
        if string.find(' '.join(cmd), ' snap ') >= 0:
            return self.vagrant_cmd.simple(cmd)
        return self.vagrant_cmd.ssh(cmd)

    def try_install_virtualbox(self):
        dest_script_file = os.path.join(self.basedir, 'install-virtualbox.sh')
        self.factory.addStep(StringDownload(
"""
#!/usr/bin/env bash

if [ -z "`which VBoxManage`" ]; then
    os=`facter operatingsystem`
    lsb=`facter lsbdistcodename`
    if echo $os | egrep 'Ubuntu|Debian'; then
        sudo bash -c "echo deb http://download.virtualbox.org/virtualbox/debian $lsb contrib >> /etc/apt/sources.list"
        sudo apt-get install curl -y
        curl -s http://download.virtualbox.org/virtualbox/debian/oracle_vbox.asc > /tmp/oracle_vbox.asc
        sudo apt-key add /tmp/oracle_vbox.asc
        sudo apt-get update
        sudo apt-get install dkms -y
        sudo apt-get install linux-headers-$(uname -r) -y
        sudo apt-get install virtualbox-4.1 -y
    else
        echo 'Only debian based' >&2
        exit 2
    fi
fi
""",  slavedest=dest_script_file))
        if self.vm:
            self.factory.addStep(ShellCommand(
                command = self.vagrant_cmd.simple(['cp', os.path.join('/','vagrant','install-virtualbox.sh'),
                                                   dest_script_file ]),
                description = 'Installing Script',
                descriptionDone = 'Script Installed',))
                             
        self.factory.addStep(ShellCommand(
                command = self.vagrant_cmd.simple(['bash', dest_script_file]),
                workdir = 'build',
                description = 'Installing VirtualBox',
                descriptionDone = 'VirtualBox Done'))

    def make_uniq_initial_name(self):
        vm = self.vm
        counter = 0
        while vm:
            vm = vm.vm
            counter += 1
        return str(counter)

