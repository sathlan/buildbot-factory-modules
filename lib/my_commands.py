import string

class Commands():
    def __init__(self, vm = None):
        self.vm = vm
        if vm:
            self.run_on_vm = True
        else:
            self.run_on_vm = False

    def with_bash(self, cmd):
        return ['bash', '-c', ' '.join(cmd)]

    def basic(self, cmd=[]):
        if self.run_on_vm:
            command = self.vm.command_prefix(cmd)
        else:
            command = self.myquote(cmd, -1)
        return command

    def subquote(self, cmd_str, level):
        bash_idx = 0
        vagrant_idx = 0
        bash_idx = string.find(cmd_str,'bash -c')
        vagrant_idx = string.find(cmd_str, 'vagrant ssh -c')
        spliter = ''
        prefix = []
        if vagrant_idx == -1 and bash_idx == -1:
            return cmd_str
        elif (bash_idx < vagrant_idx or vagrant_idx == -1) and bash_idx != -1:
            spliter = 'bash -c'
            prefix = ['bash', '-c']
        elif (vagrant_idx < bash_idx or bash_idx == -1) and vagrant_idx != -1:
            spliter = 'vagrant ssh -c'
            prefix = ['vagrant', 'ssh', '-c']
        else:
            return cmd_str

        to_be_quoted = prefix + [cmd_str.partition(spliter)[-1]]
        to_be_prepend = cmd_str.partition(spliter)[0]
        cmd_str = to_be_prepend + ' '.join(self.myquote(to_be_quoted,level))
        return cmd_str

    def myquote(self, cmd, inside):
        after_c      = False
        after_bash   = False
        after_vagrant_ssh   = False
        after_vagrant       = False
        new_cmd = []
        quoted_cmd = ''
        for element in cmd:
            if after_c:
                nbr_slash = inside
                if inside < 0:
                    next_nbr_slash = 0
                    nbr_slash      = 0
                    nbr_quote      = 0
                else:
                    next_nbr_slash = (inside * 2) + 1
                    nbr_quote       = 1
                
                quoted_cmd = '\\' * nbr_slash + '"' * nbr_quote  + self.subquote(element, next_nbr_slash) + '\\' * nbr_slash + '"' * nbr_quote
                after_c = False
                new_cmd.append(quoted_cmd)
                quoted_cmd = ''
            elif after_bash or after_vagrant_ssh:
                if element == '-c':
                    after_c = True
                after_bash = False
                after_vagrant_ssh = False
                new_cmd.append(element)
            elif after_vagrant:
                if element == 'ssh':
                    after_vagrant_ssh = True
                after_vagrant = False
                new_cmd.append(element)
            elif element == 'bash':
                after_bash = True
                new_cmd.append(element)
            elif element == 'vagrant':
                after_vagrant = True
                new_cmd.append(element)
            else:
                new_cmd.append(element)
        return new_cmd
