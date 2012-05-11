import string
import re
from error import MyCommandError

class Dummy():
    def __init__(self, name):
        self.name = name

    def basic(self, *args):
        self.throws()
    def simple(self, *args):
        self.throws()
    def ssh(self, *args):
        self.throws()
    def throws(self, *args):
        raise MyCommandError("You cannot call commands from \"%s\" use the BuilderFactory" %
                             self.name)
class Commands():
    """
    Base class to which are delegated the creation of the command list send to buildbot.

    In the ShellCommand type step, the commands are all created by a
    subclass of this class.

    Here we make sure that:
    - if the command is executed in a vm, then the command is prepend with necessary command
    - if the command starts with:
      - bash -[cs]
      - vagrant ssh -c
      - sudo vzctl exec2 \d+
      then the rest of the command will be properly quoted (using
      double quote) to the end of the command.  Nested quote are
      supported.

    There are two limititations to this process:
    1. user command should not use double quote X{"}, but single quote X{'}
    2. commands inside command (like using backquote) are executed on the slave not the vm.
    """
    def __init__(self, vm = None):
        self.vm = vm
        if vm:
            self.run_on_vm = True
        else:
            self.run_on_vm = False
        #: my_cmds is the regex which recognize the command which ask
        #: for quoting their args.
        self.my_cmds = re.compile(
            r"""(?P<pre>.*?)\s*
                (?P<cmd>bash\s+-c|vagrant\s+ssh\s+(?:[-\w_\d.]+\s+)?-c|exec\s+sudo\s+vzctl\s+exec2\s+\d+)\s*
                (?P<post>.*)""", re.X)

    def with_bash(self, cmd):
        return ['bash', '-c', ' '.join(cmd)]
    
    def basic(self, cmd=[]):
        """
        Command is executed as is in the vm.

        Basic command are transformed only for support of the underlying vm.
        """
        if self.run_on_vm:
            command = self.vm.command_prefix(cmd)
        else:
            command = self._myquote(cmd, -1)
        return command

    def ssh(self):
        """ Command executed in the VM, only need to be implemented by VM like class. """
        raise MyCommandError("Must be implemented by the caller")

    def simple(self):
        """ Command executed in the slave. Alway needed. """
        raise MyCommandError("Must be implemented by the caller")        

    def _subquote(self, cmd_str, level):
        """ Splits the command according to the L{my_cmds} regex. """
        m = re.search(self.my_cmds, cmd_str)
        if m:
            pre     = m.group('pre')
            command = m.group('cmd')
            post    = m.group('post')
        else:
            return cmd_str
        cmd_str       = pre + ' ' +\
            ' '.join(self._myquote(re.split(' +',command) + [post] ,level))
        return cmd_str

    def _myquote(self, cmd, inside):
        """ Takes care of quoting using backslash nested quote. """
        cmd_str = cmd
        if isinstance(cmd, list):
            cmd_str = ' '.join(cmd)
        m = re.match(self.my_cmds, cmd_str)
        if not m:
            return cmd
        command = re.split(' ', m.group('cmd'))
        args    = m.group('post')
        
        nbr_slash = inside
        if inside < 0:
            next_nbr_slash = 0
            nbr_slash      = 0
            nbr_quote      = 0
        else:
            next_nbr_slash = (inside * 2) + 1
            nbr_quote       = 1
            
        quoted_cmd = '\\' * nbr_slash + '"' * nbr_quote  + \
            self._subquote(args, next_nbr_slash) + '\\' * nbr_slash + '"' * nbr_quote
        
        command.append(quoted_cmd)
        return command
