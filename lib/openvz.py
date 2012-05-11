# -*- python -*-
# ex: set syntax=python:

from my_commands import Commands
from vm          import Vm
from error       import VmError

from buildbot.steps              import shell
from buildbot.process.properties import Property
from buildbot.steps.source.git   import Git
from buildbot.steps.transfer     import StringDownload

import os.path
import re

class OpenvzCommands(Commands):
    """
    Define all necessary command helpers.
    """
    def __init__(self, vzId = '', basedir = '/', vm = False):
        Commands.__init__(self, vm)
        self.vzId = str(vzId)
        self.machine = vzId
        self.basedir = basedir

    def simple(self, cmd=[], workdir = None):
        return self.basic(cmd)

    def ssh(self, cmd=[], workdir = None):
        return self.basic(['exec', 'sudo', 'vzctl', 'exec2', self.vzId] + cmd)

class Openvz(Vm):
    """
    This class support the creation of openvz vz and the execution of
    commands inside the vz.

    NOTE: It uses unavailable scripts and expect a sda4 LVM device
    available, so it's not really portable.
    """
    def __init__(self, 
                 vzId='', 
                 vzName='', 
                 vzType='VZsolo',
                 vzSize='5g',
                 vzIp='',
                 vzGw='',
                 vzLimits='enovance-nolimit.tpl',
                 vzTemplate='enovance-debian-6.0-amd64',
                 workdir = '.',
                 fix_network = True,
                 vm = None,
                 **kwds):
        self.boxname  = vzName
        self.basedir  = os.path.join('/home/vz/up/', self.boxname, 'DATA/root')
        self.vz       = str(vzId)
        Vm.__init__(self, root_vm_dir = self.basedir, vm = vm, **kwds)
        self.vzName      = vzName
        self.vzType      = vzType
        self.vzSize      = vzSize
        self.vzIp        = vzIp
        self.vzGw        = vzGw
        self.vzLimits    = vzLimits
        self.vzTemplate  = vzTemplate
        self.can_snap    = False
        self.fix_network = fix_network
        self.name        = self.boxname
#        self.name        = 'VZ ' + self.boxname
        self.property_run    = self.boxname + '_RUN'
        self.property_exists = 'VZ_INSTALLED'
        self.add_to_post_start_hook(self._fix_net)

    def init_command(self):
        self.commands = OpenvzCommands(vzId = self.vz, 
                                       basedir = self.basedir, 
                                       vm = self.vm)


    def command_prefix(self, cmd = []):
        """ Required by L{Command} class to be able to execute command in VM. """
        return self.commands.ssh(cmd)

    def install_packages(self):
        # socle is already prepared
        pass

    def install_vm(self):
        m_ip = re.match('([^/]+)/\d+', self.vzIp)
        if not m_ip:
            raise VmError("vzIp must be provided in CIDR notation XXX.XXX.XXX.XXX/XX")
        ip   = m_ip.group(1)
        self.addCreateVz(
            action   = self.vzType,
            size     = self.vzSize,
            name     = self.vzName,
            ip       = ip,
            limits   = self.vzLimits,
            template = self.vzTemplate)

    def start_vm(self):
        self.addCommandIf(
            command         = ['sudo', 'vzctl', 'start', self.vz, '--wait'],
            property_name   = self.property_run,
            description     = 'Staring VZ',
            descriptionDone = 'VZ up')

    def install_snap(self):
        pass

    def addCreateVz(
        self, 
        action='VZsolo', 
        size='5G', 
        name='my_test', 
        ip='', 
        id='1', 
        limits='enovance-nolimit.tpl', 
        template='enovance-debian-6.0-amd64'):

        self.addSetPropertyTF(
            # test if any openvz is present
            command  = ['sudo', 'vzlist', '-H', '-a', '2>/dev/null', '|', 'grep', '-q','.' ],
            property = self.property_exists)

        self.addSetPropertyTF(
            # test if the vz is running
            command  = ['sudo', 'vzlist', '-H', '-ah', self.boxname, '2>/dev/null',
                        '|', 'grep', '-q', 'running' ],
            property = self.property_run)

        self.addCommandIf(
            command         = ['sudo', 'sed', '-i','-e','s/SOLO=0/SOLO=1/',
                               '/opt/enovance/server/config_parse.sh'],
            property_name   = self.property_exists,
            description     = 'Configuring Vz 1',
            descriptionDone = 'VzConfig_1')

        self.addCommandIf(
            command         = ['sudo', 'sed', '-i','-e','s/@@HOSTNAME1@@/'+self.vzName+'/g',
                               '/opt/enovance/server/config'],
            property_name   = self.property_exists,
            description     = 'Configuring Vz 2',
            descriptionDone = 'VzConfig_2')

        self.addCommandIf(
            command         = ['sudo', 'sed', '-i','-e','s/Normal/StandAlone/g',
                               '/opt/enovance/server/config'],
            property_name   = self.property_exists,
            description     = 'Configuring Vz 3',
            descriptionDone = 'VzConfig_3')
        self.addCommandIf(
            command         = ['sudo', 'apt-get', 'install', '-y', 'drbd8-utils'],
            property_name   = self.property_exists,
            description     = 'Inst DRBD',
            descriptionDone = 'DRBD install')
        self.addDownloadFile(
            src_file = """
global {
  usage-count no;
 }


common {
    protocol C;

    startup {
        wfc-timeout 1 ;
        degr-wfc-timeout 1 ;
    }

    net {
         max-buffers 8192;
     cram-hmac-alg sha1;
     shared-secret "Hv4/lxPFXr+iJDvCNTRw00/4m2I=";
     after-sb-0pri disconnect;
     after-sb-1pri disconnect;
         after-sb-2pri disconnect;
     rr-conflict disconnect;

    }

    handlers {
        pri-on-incon-degr "echo node is primary, degraded and the local copy of the data is inconsistent | wall ";
    }

    disk {
        on-io-error pass_on;
        no-disk-barrier;
        no-disk-flushes;
        no-md-flushes;
    }

    syncer {
        rate 100M;
        al-extents 3833;
        verify-alg  crc32c;
    }

}
""",
            dst_file = '/etc/drbd.conf', as_root = True)

        self.addCommandIf(
            command         = ['sudo', '/etc/init.d/drbd', 'restart'],
            property_name   = self.property_exists,
            description     = 'Starting DRBD',
            descriptionDone = 'DrbdStart')
        self.addCommandIf(
            command         = ['sudo', 'pvcreate', '/dev/sda4'],
            property_name   = self.property_exists,
            description     = 'Creating PV',
            descriptionDone = 'PV created')
        # harcoded for VZsolo
        self.addCommandIf(
            command         = ['sudo', 'vgcreate', 'vg1','/dev/sda4'],
            property_name   = self.property_exists,
            description     = 'Creating VG',
            descriptionDone = 'VG created')
        self.addCommandIf(
            command         = ['sudo', '/opt/enovance/server/enovance-VZ-ctl',
                               action,
                               size,
                               name,
                               ip,
                               id,
                               limits,
                               template],
            property_name   = self.property_run,
            description     = 'Creating VZ',
            descriptionDone = 'VZ created')

    def _fix_net(self):
        print "FIXING NET FOR %s (%s)" % (self, self.name)
        self.addCommandIf(
            command         = ['sudo', 'bash', '-c', 'brctl addbr vzbr0' +\
                                   ' && ip l set vzbr0 up && ip a add '+\
                                   self.vzGw+' brd + dev vzbr0'],
            property_name   = self.property_run,
            description     = 'Bridging VZ',
            descriptionDone = 'VZ bridged')

        self.addCommandIf(
            command         = ['sudo', 'vzctl', 'set', self.vz, '--netif_add',
                               'eth0,,veth1.0', '--save'],
            property_name   = self.property_run,
            description     = 'Adding if to VZ',
            descriptionDone = 'VZ hw if')

        m_gw_ip = re.search('([^/]+)/\d+', self.vzGw)
        if not m_gw_ip:
            raise VmError("vzGw must be provided in CIDR notation XXX.XXX.XXX.XXX/XX")
        vz_gw_ip = m_gw_ip.group(1)

        self.addCommandInVmIf(
            command         = ['bash', '-c', " ip a add "+self.vzIp+ " brd + dev eth0" + \
                                  " && ip l set eth0 up " +\
                                  " && echo nameserver 8.8.8.8 > /etc/resolv.conf" +\
                                  ' && ip r add default via '+vz_gw_ip],
            property_name   = self.property_run,
            description     = 'Networking VZ',
            descriptionDone = 'VZ network')

        self.addCommandIf(
            command         = ['sudo', 'iptables', '-t', 'nat', '-I', 'POSTROUTING', '-o', 'eth0',
                               '-j', 'MASQUERADE'],
            property_name   = self.property_run,
            description     = 'Masquarading VZ net.',
            descriptionDone = 'VZ Masquaraded')

    def addDownloadFileFromSocle(self, src_file, dst_file, workdir = '/',
                                 on_socle = False, as_root = False):
        """
        Download a file available on the container to the VZ.

        It directly copy it into the L{basedir}.

        Can optionally be executed as root using passwordless sudo
        from the container.
        """
        dst_file_final     = dst_file
        if os.path.isabs(dst_file_final):
            dst_file_final = os.path.relpath(dst_file_final, '/')

        dst_file_final     = os.path.join(self.basedir, dst_file_final)
        self.addCpFile(src_file, dst_file_final, as_root)

    def addDownloadDirectory(self, src_dir, dst_dir, as_root = False):
        """
        Download a directory available on the container to the VZ.

        It directly copy it into the L{basedir} in the desire directory.

        Can optionally be executed as root using passwordless sudo
        from the container.
        """
        dst_dir_final     = dst_dir
        if os.path.isabs(dst_dir_final):
            dst_dir_final = os.path.relpath(dst_dir_final, '/')

        dst_dir_final     = os.path.join(self.basedir, dst_dir_final)
        self.addCpDirectory(src_dir, dst_dir_final, as_root)

    def addOpenvzCmd(self, command = [], **kwargs):
        self.addShellCmdInVm(command = command, **kwargs)

    def addCpFile(self, src_file, dst_file_final, as_root = True):
        super(Openvz, self).addCpFile(src_file, dst_file_final, True)

    def addCpDirectory(self, src_file, dst_file_final, as_root = True):
        super(Openvz, self).addCpDirectory(src_file, dst_file_final, True)
