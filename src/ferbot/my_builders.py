from buildbot.process.factory import BuildFactory

class ThisBuilder(object):

    def __init__(self, root = None, path = None, quick = False):
        print "NEW BUILDER : %s" % root
        self.root       = root
#        self.descendant = descendant
        self.path       = path
        print "THIS BUILDER %s" % self.root
        print "	Got this path : %s" % self.path
        self.quick      = quick
        self.factory    = BuildFactory()

        self.factory_name = self._set_factory_name()
        self.name       = self._set_builder_name()

    def get_quick(self):
        if self.quick:
            return '_quick'
        else:
            return ''

    def get_path(self):
        return self.path

    def _set_factory_name(self):
        obj = self.path[0]
        print "FACTORY NAME %s" % obj.name
        return obj.name

    def get_factory_name(self):
        return self.factory_name

    def _set_builder_name(self):
        name = self.get_path()[-1].name + '@' + self.get_factory_name() + self.get_quick()
        if len(self.get_path()) == 1:
            name = self.get_path()[-1].name + self.get_quick()
        return name

    def get_builder_name(self):
        return self.name

    def get_factory(self):
        return self.factory

    def set_vms(self):
        pass

    def update_vm(self):
        print "UPDATING VM of %s" % self.root
        if self.path[1:]:
            for idx, element in enumerate(self.path[1:]):
                print "	 with %s for %s" % (self.path[idx], element)
                # modify element.vm with path[idx], mind the gap!
                element.vm = self.path[idx]
        
    def update_factory(self):
        for element in self.path:
            # set element.factory to factories[current_factory]
            element.factory = self.factory
            element.init_command()
