class RvmCommands:
    def ___init__(self, ruby_version='1.8.7-p302', gemset='',prefix_cmd=[]):
        self.ruby_version = ruby_version
        self.gemset = gemset
        self.prefix_cmd = prefix_cmd

    def create(self, cmd=[], sep=';'):
        command = ['bash', '-c', 'source ~/.bash_profile; rvm use '+
                   self.ruby_version+'@'+self.gemset+' '+sep+ ' '.join(cmd)]
        if self.prefix_cmd:
            command = self.prefix_cmd + command

        return command

    def check_or_install(self, module='', version='> 0'):
        self.create(['gem', 'list', '-i', module, '-v', "'"+version+"'",
                     '||','gem','install',module,+'-v', "'"+version+"'"])

class Rvm:
    def __init__(self, factory='', ruby_version='1.8.7-p302', gemset='', modules={}):
        self.factory = factory
        self.ruby_version = ruby_version
        self.gemset = gemset
        self.modules = modules
        self._init_rvm
        self.rvmcommands = RvmCommands(ruby_version=ruby_version, gemset=gemset)

    def _init_rvm(self):
        self.factory.addStep(ShellCommand(
                command = self.rvmcommands.create(['rvm gemset create ', self.gemset],'||')))
        for module, version in modules.iteritems():
            self.factory.addStep(ShellCommand(
                    description="Checking",
                    descriptionDone=module,
                    command=check_or_install(module, version)))

    def addRVMRakeCmd(self, command = '',workdir='',description='Running', descriptionDone='Done'):
        self.factory.addStep(ShellCommand(
                description = description,
                descriptionDone = descriptionDone,
                workdir = workdir,
                command = self.rvmcommands.create(['rake', command])))
