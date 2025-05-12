from .parameters import ParameterBasedType
from .log import LoggerFactory
from .packer import packer
from .misc.six import add_metaclass

TYPES_DESCRIPTIONS = {'generic'  : 'Generic module', 'functions_export': 'Such modules give functions that are useful by evaluation rules',
                      'connector': 'Suchs modules will export data to external tools',
                      'listener' : 'Such module will listen to external queries',
                      'handler'  : 'Such module will add new handlers'}

MODULE_STATE_COLORS = {'STARTED': 'green', 'DISABLED': 'grey', 'ERROR': 'red'}
MODULE_STATES = ['STARTED', 'DISABLED', 'ERROR']


class ModulesMetaClass(type):
    __inheritors__ = set()
    
    
    def __new__(meta, name, bases, dct):
        klass = type.__new__(meta, name, bases, dct)
        # This class need to implement a real role to be load
        if klass.implement:
            # When creating the class, we need to look at the module where it is. It will be create like this (in modulemanager)
            # module___global___windows___collector_iis ==> level=global  pack_name=windows, collector_name=collector_iis
            from_module = dct['__module__']
            elts = from_module.split('___')
            # Let the klass know it
            klass.pack_level = elts[1]
            klass.pack_name = elts[2]
            meta.__inheritors__.add(klass)
        return klass


@add_metaclass(ModulesMetaClass)
class Module(ParameterBasedType):
    implement = ''
    module_type = 'generic'
    
    
    @classmethod
    def get_sub_class(cls):
        return cls.__inheritors__
    
    
    def __init__(self):
        ParameterBasedType.__init__(self)
        
        self.daemon = None
        # Global logger for this part
        self.logger = LoggerFactory.create_logger('module.%s' % self.__class__.pack_name)
        
        if hasattr(self, 'pack_level') and hasattr(self, 'pack_name'):
            self.pack_directory = packer.get_pack_directory(self.pack_level, self.pack_name)
        else:
            self.pack_directory = ''
    
    
    def get_info(self):
        return {'configuration': self.get_config(), 'state': 'DISABLED', 'log': ''}
    
    
    def prepare(self):
        return
    
    
    def launch(self):
        return
    
    
    def export_http(self):
        return
    
    
    # Call when the daemon go down.
    # WARNING: maybe the daemon thread is still alive, beware
    # of the paralel data access
    def stopping_agent(self):
        pass


class FunctionsExportModule(Module):
    module_type = 'functions_export'


class ConnectorModule(Module):
    module_type = 'connector'


class ListenerModule(Module):
    module_type = 'listener'


class HandlerModule(Module):
    module_type = 'handler'
    
    
    def __init__(self):
        super(HandlerModule, self).__init__()
        from .handlermgr import handlermgr
        implement = self.implement
        if not implement:
            self.logger.error('Unknown implement type for module, cannot load it.')
            return
        handlermgr.register_handler_module(implement, self)
