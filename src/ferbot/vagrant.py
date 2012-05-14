# -*- python -*-
# ex: set syntax=python:

from os import *
import os.path
import string
import re

from vm   import Vm
from error import VmError
from my_commands import Commands

from buildbot.steps import shell
from buildbot.process.properties import Property

from buildbot.process.properties import WithProperties

VAGRANT_VERSION='1.0.2'
VAGRANT_SNAP_VERSION='0.10'

class VagrantCmds(Commands):
    """
    Define all necessary command helpers.
    """
    def __init__(self, machine = '', basedir = '/', vagrantfile = '', vm = None):
        Commands.__init__(self, vm)
        self.machine     = machine
        self.basedir     = basedir
        self.vagrantfile = vagrantfile

    def _around_command(self, cmd=[], workdir = None):
        """
        Command must be executed in the vagrant directory L{basedir}.
        Make sure it exists and that we are in it.
        """
        command =  (['bash', '-c', 
                     ' '.join([ "([ -d '" + self.basedir + \
                                    "' ] || mkdir -p '" + self.basedir+ \
                                    "') && cd '" + \
                                    self.basedir+"' && "] + \
                                  cmd)])
        return command

    def simple(self, cmd=[], workdir = None):
        """ Execute command on socle, taking care of undelying vm. """
        command =  self.basic(cmd)
        return command

    def ssh(self, cmd=[]):
        """ Execute command on the vagrant box, taking care of undelying vm. """
        command = ['vagrant', 'ssh']
        if self.machine:
            command += [ self.machine ]
        command += [ '-c' ]
        return self.simple(self._around_command(command + [' '.join(cmd)]))

    def snap(self, command = '', snap=''):
        """ Snap the VM taking care of the required subcommands. """
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
        return self._around_command(cmd)
        
    def up(self):
        """ Starts the vm. """
        cmd = ['exec', 'vagrant', 'up']
        if self.machine:
            cmd += [ self.machine ]
        return self._around_command(cmd)

    def init(self, boxname, boxurl = None):
        """ Initialize the vagrant box. """
        cmd = ['[ -e ',self.vagrantfile, ']','||','vagrant', 'init', boxname]
        if boxurl:
            cmd += [boxurl]
        return self._around_command(cmd)

    def snap_exists(self, snap = ''):
        """ Raw Command on the socle for property testing. """
        cmd = self.__make_vagrant_output_test(['snap', 'list'], snap)
        return cmd

    def vm_is_running(self):
        """ Raw Command on the socle for property testing. """
        cmd = self.__make_vagrant_output_test(['status'], 'running')
        return cmd

    def __make_vagrant_output_test(self, cmd = [], grep= '_does_not_existssss'):
        """ Raw Command on the socle for property testing. """
        cmd_prefix = [ 'vagrant' ] + cmd
        if self.machine:
            cmd_prefix += [ self.machine ]
        command = [' '.join(cmd_prefix) + ' 2>/dev/null | egrep -q ' + grep]
        return self._around_command(command)
        
class Vagrant(Vm):
    """
    This class support the creation, snapshoting of vagrant box and
    the execution of commands inside the vagrant box.

    The Vagrantifle can be taken from a simple X{init} command or from
    a git directory.

    With this latter option multiple vm environment and provisionning
    can be setup.
    """
    def __init__(self,
                 #: where the vm directory is
                 basedir            = '',
                 #: the name used by vagrant init, when the box is on
                 #: the slave.
                 boxname            = None,
                 #: the url where the vagrant box is.
                 boxurl             = None,
                 #: the url where the vagrant definition is.  Only support Git.
                 vagrant_src        = None,
                 #: in multivm, we need the machine's name
                 machine            = None,
                 #: The name of the vagrantfile
                 vagrantfile        = 'Vagrantfile',
                 #: running on a vm?
                 vm                 = None,
                 **kwargs):

        self.boxname            = boxname
        self.basedir            = os.path.expanduser(basedir)
        self.vagrantfile        = path.join(self.basedir, vagrantfile)
        self.machine            = machine
        if self.boxname == None and self.machine:
            self.boxname = self.machine # TODO: improve the logic.
        box_m = re.match("^[-\w_\d.]+$", self.boxname)
        if not box_m:
            raise VmError("The name of the box (%s) can only contain [-\w_\d.]+" % self.boxname)
        self.vagrant_src        = vagrant_src
        # MRO should kick in both Vm, and Base, and I should use new style class:
        # http://www.python.org/doc/newstyle/
        Vm.__init__(self, root_vm_dir = self.basedir, vm = vm, **kwargs)

        self.boxurl             = boxurl
        self.can_snap           = True
        #: determine if the "package" steps are executed.
        self.property_exists    = self.name + '_EXI'
        #: determine if the "install" and "run" steps are executed.
        self.property_run       = self.name + '_RUN'

        # The root VM should snap
        if self.run_on_vm:
            self.can_snap = False

    def init_command(self):
        self.commands = VagrantCmds(machine = self.machine, 
                                    basedir = self.basedir, 
                                    vagrantfile = self.vagrantfile, 
                                    vm = self.vm)
        
    def command_prefix(self, cmd = []):
        """ Required by L{Command} class to be able to execute command in VM. """
        return self.commands.ssh(cmd)

    # TODO : need to support more os
    def install_packages(self):
        """
        Required by L{Base}.

        Install all the packages necessary to make vagrant works.  It
        only works on ubuntu and debian for the moment.
        """
        self.addSetPropertyTF(
            # test if any vagrant gem is present
            command  = ['gem', 'list', '-i', 'vagrant', "'"+VAGRANT_VERSION+"'", '>/dev/null' ],
            property = self.property_exists)

        dest_script_file         = '/tmp/install-virtualbox.sh'
        dest_script_file_content = """
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
"""
        self.addDownloadFile(src_file = dest_script_file_content,
                             dst_file = dest_script_file)
        self.addCommandIf(
            command         = ['bash', dest_script_file],
            property_name   = self.property_exists,
            workdir         = 'build',
            description     = 'Installing VirtualBox',
            descriptionDone = 'VirtualBox Done')

        self.addCommandIf(
            command         = ['bash', '-c',
                ' '.join(['gem', 'list', '-i', 'vagrant', '-v', "'"+VAGRANT_VERSION+"'", '||',
                          'sudo', 'gem', 'install', 'vagrant', '-v', "'"+VAGRANT_VERSION+"'"])],
            property_name   = self.property_exists,
            description     = 'Installing Vagrant',
            descriptionDone = 'Vagrant installed')

    def install_vm(self):
        """
        Required by L{Base}.

        Install all the vagrant box.
        """
        self.addSetPropertyTF(
            # test if the vagrant box is running
            command  = self.commands.vm_is_running(),
            property = self.property_run)

        if self.vagrant_src and self.vagrant_src.startswith("git"):
            # if the '.vagrant' file is not in the .gitignore it will
            # be deleted, so it must be added (manually)
            self.addDownloadGitDir(repo_url = self.vagrant_src,
                                   dest_dir = self.basedir,
                                   use_new  = True)
        elif self.boxname:
            self.addCommandIf(
                    description     = 'Initializing ' + self.name,
                    descriptionDone = self.name + ' initialized',
                    property_name   = self.property_run,
                    command         = self.commands.init(self.boxname,self.boxurl))
        else:
            raise VmError("Cannot find the source of the Vagrant box.")

    def start_vm(self):
        """
        Required by L{Base}.

        Start the vagrant box.
        """
        self.addCommandIf(
            description     = 'Starting '+self.name,
            descriptionDone = self.name + ' up',
            command         = self.commands.up(),
            property_name   = self.property_run)
        self.addCommandInVmIf(
            command         = ['sudo', 'bash', '-c',
                               # strange form because things like echo
                               # $HOSTNAME >> ..  won't work as
                               # HOSTNAME is evaluated on the slave...
                               'uname -n | sed -Ee s/\(.*\)/127.0.0.1\ \\1/ >> /etc/hosts'],
            description     = 'Fixing resolv',
            descriptionDone = 'resolv Fixed',
            property_name   = self.property_run)

    def install_snap(self):
        """
        Required by L{Base}.

        Install the package necessary for snapping.
        """
        self.addCommandIf(
            command         = self.commands.with_bash(
                ['gem', 'list', '-i virtualbox', '||',
                 'sudo', 'gem', 'install', 'virtualbox']),
            description     = 'Installing VB for '+self.name ,
            descriptionDone = 'virtualbox '+self.name,
            property_name   = self.property_exists)
        self.addCommandIf(
            command         = self.commands.with_bash(
                ['gem', 'list', '-i      vagrant-snap -v', "'"+VAGRANT_SNAP_VERSION+"'", '||',
                 'sudo', 'gem', 'install vagrant-snap -v', "'"+VAGRANT_SNAP_VERSION+"'"]),
            description     = 'Installing Snap for ' + self.name,
            descriptionDone = 'Snap installed for ' + self.name,
            property_name   = self.property_exists)

    def addDownloadDirectory(self, src_dir, dst_dir, as_root = False):
        """ 
        Download a directory available on the slave to the vagrant box.

        It does it in two steps:
        1. by default the L{basedir} is shared on vagrant, so first
           copy the directory in the X{upload} subdirectory.
        2. Then execute a copy inside the vagrant to put the directory
           inside its final destination, destroying it before.

        Can optionally be executed as root using passwordless sudo.
        """
        dir_in_vm = '/upload/'+ dst_dir
        # TODO: handles relative and absolute dirname.
        # TODO: make the dir name unique, see next TODO
        tmp_dir   = self.basedir + dir_in_vm
        # TODO: WithProperties %(buildername)s-%(buildnumber)s' does not work.
        # To upload I just copy to the root vagrant dir as it is shared
        self.addCpDirectory(src_dir + '/', tmp_dir)
        self.addCpDirectoryInVm('/vagrant' + dir_in_vm + '/', dst_dir, as_root)
        return dst_dir

    def addDownloadFileFromSocle(self, src_file, dst_file, workdir = '/',
                                 on_socle = False, as_root = False):
        """
        Download one file from socle to the vagrant box.

        Required by L{Base} to make addDownloadFile works.

        The steps are roughtly the same as for the
        L{addDownloadDirectory}.
        """
        dst_file_rel = dst_file
        workdir_rel  = workdir

        if os.path.isabs(dst_file):
            dst_file_rel = os.path.relpath(dst_file,'/')
        if os.path.isabs(workdir):
            workdir_rel  = os.path.relpath(workdir,'/')
            
        dst                 = os.path.join('/',workdir_rel, dst_file_rel)
        file_in_vm          = os.path.join('upload', dst_file_rel)
        tmp_file            = os.path.join(self.basedir, file_in_vm)
        file_in_vm_on_share = os.path.join('/vagrant',file_in_vm)

        if on_socle:
            self.addCpFile(src_file, dst_file, as_root)
            return dst_file

        self.addCpFile(src_file, tmp_file, False) # tmp file
        cmd = ['bash', '-c','mkdir', '-p', os.path.dirname(dst), '&&',
               'cp', '-vf', file_in_vm_on_share, dst]
        if as_root:
            cmd = [ 'sudo' ] + cmd

        self.addShellCmdInVm(command         = cmd,
                             description     = 'Uploading file.',
                             descriptionDone = 'File uploaded')
        return dst_file

