from opsbro.module import FunctionsExportModule

# Import modules to get core functions
import filesystem
import network
import packages
import system
import ftimes
import node
import frandom
import fhash


class CoreFunctionsModule(FunctionsExportModule):
    implement = 'corefunctions'
    manage_configuration_objects = []
    
    
    def __init__(self):
        FunctionsExportModule.__init__(self)
    
    
    def get_info(self):
        return {}
