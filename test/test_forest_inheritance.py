from unittest import TestCase
from flexmock import flexmock
from ferbot.error import MyFactoryError
from ferbot.dummy_vm import DummyVm  # import Base
from ferbot.dummy import Dummy  # import Base
from ferbot.error import MyCommandError

''' Test the base class '''

class ForestInheritance(TestCase):
    def setUp(self):
        self.dummy_vm   = DummyVm(boxname='test_1_vm',vms=[], force_new_builders = True)
        self.dummy_1    = Dummy(directory='test_1',vms=[self.dummy_vm])
        self.dummy_2    = Dummy(directory='test_2',vms=[self.dummy_vm])
        

    def test_compile_base(self):
        self.assertEquals("test_1@name", self.dummy_1.name)
        self.assertEquals(False, self.dummy_1.is_vm)
        self.assertEquals(True, self.dummy_1.run_on_vm)
        self.assertEquals("test_2@name", self.dummy_2.name)
        self.assertEquals(False, self.dummy_2.is_vm)
        self.assertEquals(True, self.dummy_2.run_on_vm)
        self.assertEquals("test_1_vm", self.dummy_vm.name)
        self.assertEquals(True, self.dummy_vm.is_vm)

    def test_commands_base(self):
        self.assertRaises(MyCommandError, self.dummy_vm.commands.simple)
        
    def test_start_base(self):
        self.builders = self.dummy_1.start()
        self.assertRaises(MyFactoryError, self.dummy_2.start)
        self.assertEquals(set([self.dummy_1, self.dummy_2]), self.builders.roots())
        self.assertEquals(2, len(self.builders.roots()))
        self.assertEquals(['dummyvm','ssh',' bash -c "source test_1/dummy ; onetest"'],
                          self.dummy_1.commands.simple(['onetest']))
        self.assertEquals(['dummyvm','ssh',' bash -c "source test_2/dummy ; twotest"'],
                          self.dummy_2.commands.simple(['twotest']))
        self.assertItemsEqual(
            ['test_2@name@test_1_vm',       'test_1@name@test_1_vm',
             'test_2@name@test_1_vm_quick', 'test_1@name@test_1_vm_quick', ],
            self.builders.get_builders_name())
        self.assertEquals({'nbr_of_elements': 8, 'nbr_of_steps': 12, 'nbr_of_chains': 4},
                          self.dummy_1.stats)
