from unittest import TestCase
from flexmock import flexmock
from ferbot.dummy_vm import DummyVm  # import Base
from ferbot.error import MyCommandError

''' Test the Vm class '''

class TestVm(TestCase):
    def setUp(self):
        self.dummy_vm  = DummyVm(boxname='test_vm@vm',vms=[], force_new_builders = True)

    def test_compile(self):
        self.assertEquals('test_vm@vm', self.dummy_vm.name)
        self.assertEquals(True, self.dummy_vm.is_vm)
        self.assertEquals(False, self.dummy_vm.run_on_vm)
        self.assertEquals(True, self.dummy_vm.can_snap)

    def test_commands(self):
        self.assertRaises(MyCommandError, self.dummy_vm.commands.simple)
        
    def test_start(self):
        self.builders = self.dummy_vm.start()
        self.assertEquals(set([self.dummy_vm]),self.builders.roots())
        self.assertEquals(1, len(self.builders.roots()))
        self.assertEquals(['dummyvm', 'ssh', 'onetest'],
                          self.dummy_vm.commands.ssh(['onetest']))
        self.assertItemsEqual(['test_vm@vm', 'test_vm@vm_quick'],
                          self.builders.get_builders_name())
        self.assertEquals({'nbr_of_elements': 2, 'nbr_of_steps': 4, 'nbr_of_chains': 2},
                          self.dummy_vm.stats)
