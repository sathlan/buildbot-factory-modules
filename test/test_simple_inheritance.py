from unittest import TestCase
from flexmock import flexmock
from ferbot.dummy_vm import DummyVm  # import Base
from ferbot.dummy import Dummy  # import Base
from ferbot.error import MyCommandError

''' Test the base class '''

class SimpleInheritance(TestCase):
    def setUp(self):
        self.dummy_vm  = DummyVm(boxname='test_s_vm',vms=[], force_new_builders = True)
        self.dummy    = Dummy(directory='test_s',vms=[self.dummy_vm])
        
    def test_compile_base(self):
        self.assertEquals("test_s@name", self.dummy.name)
        self.assertEquals(False, self.dummy.is_vm)
        self.assertEquals("test_s_vm", self.dummy_vm.name)
        self.assertEquals(True, self.dummy_vm.is_vm)
        self.assertEquals(True, self.dummy.run_on_vm)

    def test_commands_base(self):
        self.assertRaises(MyCommandError, self.dummy.commands.simple)
        
    def test_start_base(self):
        self.builders = self.dummy.start()
        self.assertEquals(set([self.dummy]), self.builders.roots())
        self.assertEquals(1, len(self.builders.roots()))
        self.assertEquals(True, self.dummy.commands.run_on_vm)
#        self.assertEquals('toto', self.dummy.commands.vm.command_prefix(['tutu']))
        self.assertEquals(['dummyvm','ssh',' bash -c "source test_s/dummy ; onetest"'],
                          self.dummy.commands.simple(['onetest']))
        self.assertEquals(['test_s@name@test_s_vm', 'test_s@name@test_s_vm_quick'],
                          self.builders.get_builders_name())
        self.assertEquals({'nbr_of_elements': 4, 'nbr_of_steps': 6, 'nbr_of_chains': 2},
                          self.dummy.stats)

    def test_check_steps(self):
        self.builders = self.dummy.start()
        all_steps_expected = {'test_s@name@test_s_vm': 
                              [['bash',
                                '-c',
                                ' bash -c "exit 0  && echo TRUE" || echo FALSE'],
                               ['test1_vm', 'snap', 'take'],
                               ['dummyvm',
                                'ssh',
                                ' bash -c "sudo dummy completeinstall"'],
                               ['test1_vm', 'snap', 'go'],
                               ['test1_vm', 'snap', 'take']],
                              'test_s@name@test_s_vm_quick': [['test1_vm', 'snap', 'go']]}
        self.assertEquals(all_steps_expected, self.dummy.builderfactory.get_all_steps_command())

