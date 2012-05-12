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


    def get_quick(self):
        if self.quick:
            return '_quick'
        else:
            return ''

    def get_path(self):
        return self.path

    def get_factory_name(self):
        obj = self.path[0]
        self.factory_name = obj.name
        return self.factory_name

    def get_builder_name(self):
        print "DEBUG: builder name %s" %  self.get_path()[-1].name + '@' + self.get_factory_name() + self.get_quick()
        return self.get_path()[-1].name + '@' + self.get_factory_name() + self.get_quick()

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
