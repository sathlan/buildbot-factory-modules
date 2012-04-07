# Try schedule does not work with the new git module
# version 0.8.5 12/21/04
from error import MyFactoryError

from buildbot.steps.source import Git as GitOld
# from buildbot.steps.slave import MakeDirectory # require buildbot 0.8.6!
from buildbot.steps.slave import RemoveDirectory
from buildbot.steps.shell import ShellCommand

import tempfile

class Base():
    def __init__(self, commands = ''):
        self.commands = commands

    """ Upload to a dir a Git(+patch) repository.  Support any number of underlying VM """
    def addUploadGitDir(self, repo_url = '', dest_dir = '', mode='copy', steps = []):
        if self.vm:
            this_step = steps +\
                [lambda src_dir,dst_dir,s=self.vm: s.addUploadDirectory(src_dir, dst_dir)]
            print "BASE: inside VM" + str(len(this_step))
            self.vm.addUploadGitDir(repo_url = repo_url,
                                    dest_dir = dest_dir,
                                    mode = mode,
                                    steps = this_step)
            print "BASE: after VM" + str(len(this_step))
        else:
            print "BASE: not in VM"
            self.factory.addStep(GitOld(repourl=repo_url, mode=mode))
            iter_dir = False
            last = len(steps)
            cmpt = 1
            if last == 0:
                # not any vm, but still have to mv dir to dst
                self.addUploadDirectory('.', dest_dir)
            for step in steps:
                final_dst = '/tmp'+ dest_dir
                if cmpt == last:
                    final_dst = dest_dir
                if not iter_dir:
                    iter_dir = step('../build', final_dst) # directory where the src is.
                else:
                    iter_dir = step(iter_dir, final_dst)

    def addMakeDirectory(self, directory):
        self.factory.addStep(ShellCommand(
            command = self.commands.basic('mkdir','-p', directory),
            description = 'Creating ' + directory,
            descriptionDone = directory,))

    def addCpDirectory(self, src_dir, dst_dir):
        self.factory.addStep(ShellCommand(
            command = self.commands.basic(['bash', '-c', ' '.join(['rm','-rf', dst_dir, '&&',
                           'mkdir', '-p', dst_dir, '&&', 
                           'cp', '-a',src_dir, dst_dir])]),
            description = 'Copying Dir',
            descriptionDone = 'Dir Copied'))
