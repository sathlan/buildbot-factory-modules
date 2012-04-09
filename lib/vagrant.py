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

from buildbot.process.properties import WithProperties

VAGRANT_VERSION='1.0.2'
VAGRANT_SNAP_VERSION='0.10'

class VagrantCmds(Commands):
    def __init__(self, machine = '', basedir = '/', vm = None):
        Commands.__init__(self, vm)
        self.machine = machine
        self.basedir = basedir

    def around_command(self, cmd=[], workdir = None):
        """ Helper command """
        command =  (['bash', '-c', ' '.join([ "([ -d '" + self.basedir + \
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
        """ Execute command on the vz, taking care of undelying vm. """
        print "DEBUG: SSH"
        command = ['vagrant', 'ssh']
        if self.machine:
            command += [ self.machine ]
        command += [ '-c' ]
        return self.simple(self.around_command(command + [' '.join(cmd)]))

    # helpers
    def snap(self, command = '', snap=''):
        """ Command on the socle. """
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
        return self.around_command(cmd)
        
    def up(self):
        """ Command on the socle. """
        cmd = ['exec', 'vagrant', 'up']
        if self.machine:
            cmd += [ self.machine ]
        return self.around_command(cmd)

    def init(self, boxname, boxurl = False):
        """ Command on the socle. """
        cmd = ['vagrant', 'init', boxname]
        if boxurl:
            cmd += [boxurl]
        return self.around_command(cmd)

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
        return self.around_command(command)
        
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
        self.boxurl= boxurl
        self.name = 'VAGRANT' + self.make_uniq_initial_name()
        self.fix_network = fix_network
        self.can_snap = True
        # The root VM should snap
        if self.run_on_vm:
            self.can_snap = False

    def addDownloadDirectory(self, src_dir, dst_dir):
        """ Must be provided to upload a dir to the vm """
        dir_in_vm = '/upload/'+ dst_dir
        # TODO: make the dir name unique, see next TODO
        tmp_dir = self.basedir + dir_in_vm
        # TODO: WithProperties %(buildername)s-%(buildnumber)s' may work.
        # To upload I just copy to the root vagrant dir as it is shared
        print "		DEBUG: uploaddir: cp " + src_dir + "/ and dst " + tmp_dir
        self.addCpDirectory(src_dir + '/', tmp_dir)
        print "		DEBUG: uploaddir: ssh cp " + '/vagrant' + dir_in_vm + "/ and dst " + dst_dir
        self.addCpDirectoryInVm('/vagrant' + dir_in_vm + '/',dst_dir)
#        self.factory.addStep(ShellCommand(
#                command = self.vagrant_cmd.ssh(['cp','-a', '/vagrant' + dir_in_vm + '/', dst_dir]),
#                description = 'Uploading',
#                descriptionDone = 'Uploaded'))
        print "		DEBUG: UPLOADDIRECTORY: return " + dst_dir
        return dst_dir

    def addDownloadFileFromSocle(self, src_file, dst_file, workdir = '/', on_socle = False):
        dst_file_rel = dst_file
        workdir_rel  = workdir

        if os.path.isabs(dst_file):
            dst_file_rel = os.path.relpath(dst_file,'/')
        if os.path.isabs(workdir):
            workdir_rel = os.path.relpath(workdir,'/')
            
        dst = os.path.join('/',workdir_rel, dst_file_rel)
        file_in_vm = os.path.join('upload', dst_file_rel)
        tmp_file   = os.path.join(self.basedir, file_in_vm)
        file_in_vm_on_share = os.path.join('/vagrant',file_in_vm)
        if on_socle:
            self.addCpFile(src_file, dst_file)
            return dst_file

        self.addCpFile(src_file, tmp_file)
        self.addShellCmdInVm(command = ['bash', '-c','mkdir', '-p',
                                        os.path.dirname(dst), '&&',
                                        'cp', '-f', file_in_vm_on_share, dst],
                             description = 'Uploading file.',
                             descriptionDone    = 'File uploaded')
        return dst_file

    def add_pre_command(self, commands=[]):
        for cmd in commands:
            self.pre_commands_hook.append(cmd)

    def command_prefix(self, cmd = []):
        return self.vagrant_cmd.ssh(cmd)

    # TODO : need to support more os
    def install_packages(self):
        self.addSetPropertyTF(command = self.commands.with_bash(
                ["facter operatingsystem | egrep -q 'Ubuntu|Debian'"]),
                              property = 'IS_DEBIAN')

        dest_script_file = '/tmp/install-virtualbox.sh'
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
                command = ['bash', dest_script_file],
                property_name = 'IS_DEBIAN',
                true_or_false = 'TRUE',
                workdir = 'build',
                description = 'Installing VirtualBox',
                descriptionDone = 'VirtualBox Done')

        self.addShellCmd(
            command = self.commands.with_bash([
                'gem', 'list', '-i vagrant -v', "'"+VAGRANT_VERSION+"'", '||',
                'sudo', 'gem', 'install vagrant -v', "'"+VAGRANT_VERSION+"'"]),
            description='Installing Vagrant',
            descriptionDone='Vagrant installed')

    def install_snap(self):
        self.addShellCmd(
            command = self.commands.with_bash(['gem', 'list', '-i virtualbox', '||',
                                              'sudo', 'gem', 'install', 'virtualbox']),
            description='Installing VB for '+self.name ,
            descriptionDone='virtualbox '+self.name,)
        self.addShellCmd(
                command= self.commands.with_bash(
                ['gem', 'list', '-i vagrant-snap -v', "'"+VAGRANT_SNAP_VERSION+"'", '||',
                 'sudo', 'gem', 'install vagrant-snap -v', "'"+VAGRANT_SNAP_VERSION+"'"]),
                description='Installing Snap for ' + self.name,
                descriptionDone='Snap installed for' + self.name)

    def make_uniq_initial_name(self):
        vm = self.vm
        counter = 0
        while vm:
            vm = vm.vm
            counter += 1
        return str(counter)

    def fix_net(self):
        self.addShellCmdInVm(command = ['sudo', 'dhclient', 'eth0'],
                             description = 'Fixing Net',
                             descriptionDone = 'Network Fixed')
        
    def install_vm(self):
        self.addSetPropertyTF(
                command=['[ -e ' + self.vagrantfile + ' ]'],
                description='Setting property',
                property=self.name+'_is_installed')

        self.addCommandIf(
                command = ['mkdir', '-p', self.basedir],
                description = 'Creating base dir',
                descriptionDone = 'Dir created',
                property_name = self.name+'_is_installed')

        self.addSetPropertyTF(
                command=self.commands.vm_is_running(),
                description='Setting property',
                property=self.name+'_is_running')

        if self.vagrantfile_source:
            # if the '.vagrant' file is not in the .gitignore it will
            # be deleted, so it must be added (manually)
            self.addUploadGitDir(rep_ourl = self.vagrantfile_source,
                                 dest_dir = self.basedir,
                                 use_new = True)
        elif self.boxname:
            self.addCommandIf(
                    description='Initializing '+self.name,
                    descriptionDone=self.name + ' initialized',
                    property_name = self.name+'_is_installed',
                    command = self.vagrant_cmd.init(self.boxname,self.boxurl))

    def start_vm(self):
        cmd = self.vagrant_cmd.up()
        self.addCommandIf(
                description='Starting '+self.name,
                descriptionDone=self.name + ' up',
                command = cmd,
                doStepIf = self.name+'_is_running')
