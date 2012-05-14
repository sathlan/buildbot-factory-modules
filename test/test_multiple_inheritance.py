from unittest import TestCase
from flexmock import flexmock
from ferbot.error import MyFactoryError
from ferbot.dummy_vm import DummyVm  # import Base
from ferbot.dummy import Dummy  # import Base
from ferbot.error import MyCommandError

''' Test the base class '''

class ForestInheritance(TestCase):
    def setUp(self):
        self.dummy_vm_1   = DummyVm(boxname='test_1_vm_mh',vms=[], force_new_builders = True)
        self.dummy_vm_2   = DummyVm(boxname='test_2_vm_mh',vms=[])
        self.dummy_1    = Dummy(directory='test_mh',vms=[self.dummy_vm_1, self.dummy_vm_2])

    def test_start_base(self):
        self.builders = self.dummy_1.start()
        self.assertEquals(set([self.dummy_1]), self.builders.roots())
        self.assertEquals(1, len(self.builders.roots()))
        self.assertItemsEqual(['test_mh@name@test_2_vm_mh',
                           'test_mh@name@test_1_vm_mh',
                           'test_mh@name@test_2_vm_mh_quick',
                           'test_mh@name@test_1_vm_mh_quick'],
                          self.builders.get_builders_name())
        self.assertEquals({'nbr_of_elements': 8, 'nbr_of_steps': 7, 'nbr_of_chains': 4},
                          self.dummy_1.stats)
