from unittest import TestCase
from flexmock import flexmock
from ferbot.dummy import Dummy  # import Base
from ferbot.error import MyCommandError

''' Test the base class '''

class BaseTest(TestCase):
    def setUp(self):
        self.factory  = []
        self.dummy = Dummy(directory='test',vms=[], force_new_builders = True)

    def test_compile_base(self):
        self.assertEquals("test@name", self.dummy.name)
        self.assertEquals(False, self.dummy.is_vm)

    def test_commands_base(self):
        self.assertRaises(MyCommandError, self.dummy.commands.simple)
        
    def test_start_base(self):
        self.builders = self.dummy.start()
        self.assertEquals(set([self.dummy]), self.builders.roots())
        self.assertEquals(1, len(self.builders.roots()))
        self.assertEquals(['bash', '-c', 'source test/dummy ; onetest'],
                          self.dummy.commands.simple(['onetest']))
        self.assertItemsEqual(['test@name', 'test@name_quick'],
                          self.builders.get_builders_name())
        self.assertEquals({'nbr_of_elements': 2, 'nbr_of_steps': 1, 'nbr_of_chains': 2},
                          self.dummy.stats)

