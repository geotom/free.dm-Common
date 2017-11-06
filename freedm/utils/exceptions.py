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
    def __init__(self, handler: str):
        try:
            method = getattr(self.__class__, f'{handler}Handler')
            if hasattr(method, '__call__'):
                sys.excepthook = method
            else:
                sys.excepthook = self.__class__.defaultHandler
        except:
            sys.excepthook = self.__class__.defaultHandler 
        
    @staticmethod
    def defaultHandler(exctype, value, traceback) -> None:
        print(f'ERROR: "{exctype.__name__}" TEXT: "{value}"')
    
    @staticmethod
    def productHandler(exctype, value, traceback) -> None:
        print(f'ERROR: "{exctype.__name__}" TEXT: "{value}"')
            
    @staticmethod
    def debugHandler(exctype, value, traceback) -> None:
        print(f'ERROR: "{exctype.__name__}" TEXT: "{value}"')
        sys.__excepthook__(exctype, value, traceback)
