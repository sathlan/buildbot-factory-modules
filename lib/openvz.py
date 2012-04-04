# -*- python -*-
# ex: set syntax=python:

from my_commands import Commands

from buildbot.steps import shell
from buildbot.process.properties import Property
from buildbot.steps.shell import ShellCommand
from buildbot.steps.source.git import Git
from buildbot.steps.transfer import StringDownload

class OpenvzCommands(Commands):
    def __init__(self, vzId = '', vm=False):
        Commands.__init__(self, vm)
        self.vzId = str(vzId)

    def simple(self, cmd=[]):
        return self.basic(cmd)

    def vzExec(self, cmd=[]):
        return self.basic(['exec', 'sudo', 'vzctl', 'exec2', self.vzId] + cmd)

class Openvz:
    def __init__(self, 
                 factory = '', 
                 vzId='', 
                 vzName='', 
                 vzType='VZsolo',
                 vzSize='5g',
                 vzIp='',
                 vzLimits='enovance-nolimit.tpl',
                 vzTemplate='enovance-debian-6.0-amd64',
                 want_init_snap_named='openvz_setup',
                 workdir = '.',
                 vm = False):
        self.factory = factory
        self.vz      = str(vzId)
        self.vzName  = vzName
        self.vzType  = vzType
        self.vzSize  = vzSize
        self.vzIp    = vzIp
        self.vzLimits = vzLimits
        self.vzTemplate = vzTemplate
        self.workdir    = workdir
        if vm:
            self.workdir = vm.basedir

        self.openvzcmd = OpenvzCommands(vzId = self.vz, vm = vm)

        self.want_init_snap_named=want_init_snap_named
        self.pre_commands_hook=[]
        self.vm = vm

    def init_snap(self, name=''):
        self.want_init_snap_named = name

    def add_pre_command(self,commands=[]):
        for cmd in commands:
            self.pre_commands_hook.append(cmd)

    def start(self):
        property_name = self.want_init_snap_named
        if self.vm:
            self.vm.init_snap(property_name)
            self.vm.start()

        self.addCreateVz(
            action   = self.vzType,
            size     = self.vzSize,
            name     = self.vzName,
            ip       = self.vzIp,
            limits   = self.vzLimits,
            template = self.vzTemplate,
            vz_snap  = self.want_init_snap_named,)

        while self.pre_commands_hook:
            command = self.pre_commands_hook.pop()
            self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(command),
                description = 'Running Pre-Hook', 
                descriptionDone='Pre-Hook',
                wordir = self.basedir,
                doStepIf = lambda s,name=property_name: s.getProperty(name, 'FALSE') == 'FALSE'))

        if self.vm:
            self.vm.addTakeSnap(property_name)

    def addOpenvzCmd(self,
                     cmd = [],
                     description = 'Running',
                     descriptionDone = 'Done',
                     timeout = 1200,
                     doStepIf = True):
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.vzExec(cmd),
                description = description,
                descriptionDone = descriptionDone,
                timeout = timeout,
                workdir = self.workdir,
                doStepIf = doStepIf))
        
        
        

    def addCreateVz(self, action='VZsolo', size='5G', name='my_test', ip='', id='1', limits='enovance-nolimit.tpl', template='enovance-debian-6.0-amd64', vz_snap='____non_exististing_snap'):
        dostepmaybe = lambda s,name=vz_snap: s.getProperty(name, 'FALSE') == 'FALSE'

        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'sed', '-i','-e','s/SOLO=0/SOLO=1/',
                                                 '/opt/enovance/server/config_parse.sh']),
                doStepIf = dostepmaybe,
                workdir  = self.workdir,
                descriptionDone = 'VzConfig_1'))
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'sed', '-i','-e','s/@@HOSTNAME1@@/'+self.vzName+'/g',
                                                 '/opt/enovance/server/config']),
                doStepIf = dostepmaybe,
                workdir  = self.workdir,
                descriptionDone = 'VzConfig_2'))

        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'sed', '-i','-e','s/Normal/StandAlone/g',
                                                 '/opt/enovance/server/config']),
                workdir  = self.workdir,
                doStepIf = dostepmaybe,
                descriptionDone = 'VzConfig_3'))
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'apt-get', 'install', '-y', 'drbd8-utils']),
                doStepIf = dostepmaybe,
                workdir  = self.workdir,
                descriptionDone = 'InstDRBD'))
        self.factory.addStep(StringDownload(
"""
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
""", slavedest='drbd.conf'))
        dest_dir = self.workdir
        if not self.vm:
            dest_dir = op.path.join('/','etc')
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'cp', 'drbd.conf', dest_dir]),
                description = 'Copying',
                doStepIf = dostepmaybe,
                descriptionDone = 'drbd.conf'))
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'cp', '/vagrant/drbd.conf', '/etc/drbd.conf']),
                doStepIf = dostepmaybe,
                workdir  = self.workdir,
                descriptionDone = 'DrbdInst'))
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', '/etc/init.d/drbd', 'restart']),
                workdir  = self.workdir,
                doStepIf = dostepmaybe,
                descriptionDone = 'DrbdStart'))
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'pvcreate', '/dev/sda4']),
                workdir  = self.workdir,
                doStepIf = dostepmaybe,
                descriptionDone = 'PV created'))
        # harcoded for VZsolo
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'vgcreate', 'vg1','/dev/sda4']),
                workdir  = self.workdir,
                doStepIf = dostepmaybe,
                descriptionDone = 'VG created'))
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', '/opt/enovance/server/enovance-VZ-ctl',
                          action,
                          size,
                          name,
                          ip,
                          id, 
                          limits,
                          template]),
                workdir  = self.workdir,
                doStepIf = dostepmaybe,
                descriptionDone = 'VZ created'))
        self.factory.addStep(ShellCommand(
                command = self.openvzcmd.simple(['sudo', 'vzctl', 'start', self.vz]),
                workdir = self.workdir,
                doStepIf = dostepmaybe,
                descriptionDone = 'VZ up'))

    def command_prefix(self, cmd = []):
        return self.openvzcmd.vzExec(new_cmd)
