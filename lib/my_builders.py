from buildbot.process.factory import BuildFactory

class ThisBuilder(object):

    def __init__(self, root = None, descendant = None, quick = False):
        print "NEW BUILDER : %s" % root
        self.root       = root
        self.descendant = descendant
        self.path       = None
        self.quick      = quick
        self.factory    = BuildFactory()


    def get_quick(self):
        if self.quick:
            return '_quick'
        else:
            return ''

    def get_path(self):
        path = [self.descendant] + self.descendant.ancestors
        self.path = path
        return path

    def get_factory_name(self):
        obj = self.path[0]
        self.factory_name = obj.name
        return self.factory_name

    def get_builder_name(self):
        print "DEBUG: builder name %s" %  self.get_path()[-1].name + self.get_factory_name()
        return self.get_path()[-1].name + self.get_factory_name() + self.get_quick()

    def get_factory(self):
        return self.factory

    def set_vms(self):
        pass

    def update_vm(self):
        for idx, element in enumerate(self.path[1:]):
            # modify element.vm with path[idx], mind the gap!
            element.vm = self.path[idx]
        
    def update_factory(self):
        for element in self.path:
            # set element.factory to factories[current_factory]
            element.factory = self.factory
            element.init_command()
