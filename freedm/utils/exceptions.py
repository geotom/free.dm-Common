'''
A utility class for exception handling.
@author: Thomas Wanderer
'''

# Imports
import sys
import platform
from typing import Union, Callable, Type


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


class freedmBaseException(Exception):
    '''
    The base class for all freedm module exceptions. A free
    '''
    
    # A template string or function for string representations of this exception
    template: Union[str, Callable] = None
    
    # A flag causing the program to halt when fatal is True
    fatal: bool = False
    
    # Prefix
    prefix: str = 'free.dm:'
    
    def __init__(self, error) -> None:
        super().__init__(error)
        
        # Print a message
        if isinstance(self.template, str):
            print(self.prefix, self.template.format(error=error))
        elif hasattr(self.template, '__call__'):
            print(self.prefix, self.template(error))
            
        # Is this a fatal exception?
        if self.fatal is True:
            sys.exit()


class freedmUnsupportedOS(freedmBaseException):
    '''
    Gets thrown when the current OS is not supported
    '''
    
    def template(self, error: Type[Exception]) -> str:
        if error.name:
            return f'Module "{error.name}" not supported on current Operating System "{platform.system()}"'
        else:
            return f'Module not supported on current Operating System "{platform.system()}" ({error})'


class freedmModuleImport(freedmBaseException):
    '''
    Gets thrown when a Python module cannot be imported
    '''
    def __init__(self, error) -> None:
        super().__init__(error)
        if error.name:
            print(f'Missing module dependency ({error.name}): Please install via "pip install {error.name}"\nExiting...')
        else:
            print(f'Missing module dependency ({error})\nExiting...')
        sys.exit()