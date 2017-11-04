'''
A utility class for exception handling.
@author: Thomas Wanderer
'''

# Imports
import sys

class ExceptionHandler(object):
    '''
    A custom Exception handler defining a method to react on errors
    '''
    # Init
    def __init__(self, handler):
        try:
            method = getattr(self.__class__, '{0}Handler'.format(handler))
            if hasattr(method, '__call__'):
                sys.excepthook = method
            else:
                sys.excepthook = self.__class__.defaultHandler
        except:
            sys.excepthook = self.__class__.defaultHandler 
        
    @staticmethod
    def defaultHandler(exctype, value, traceback):
        print('ERROR: "{0}" TEXT: "{1}"'.format(exctype.__name__, value))
    
    @staticmethod
    def productHandler(exctype, value, traceback):
        print('ERROR: "{0}" TEXT: "{1}"'.format(exctype.__name__, value))
            
    @staticmethod
    def debugHandler(exctype, value, traceback):
        print('ERROR: "{0}" TEXT: "{1}"'.format(exctype.__name__, value))
        sys.__excepthook__(exctype, value, traceback)
