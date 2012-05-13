from unittest import TestCase
from flexmock import flexmock
from ferbot.dummy import Dummy  # import Base
from ferbot.error import MyCommandError

''' Test the base class '''

class CaseTest(TestCase):
    dummy    = Dummy(directory='test',vms=[])

    def test_compile(self):
        self.assertEquals("test@name", self.dummy.name)
        self.assertEquals(False, self.dummy.is_vm)

    def test_commands(self):
        self.assertRaises(MyCommandError, self.dummy.commands.simple)
        
    def test_start(self):
        self.builders = self.dummy.start()
        self.assertEquals(set([self.dummy]),self.builders.roots())
        self.assertEquals(['bash', '-c', 'source test/dummy ; onetest'],
                          self.dummy.commands.simple(['onetest']))
        