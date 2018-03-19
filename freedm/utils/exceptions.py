'''
A utility class for exception handling.
@author: Thomas Wanderer
'''

# Imports
import sys
import platform
from typing import Union, Callable, Type


# free.dm Imports
from . import logging


# Create logger
logger = None


class ExceptionHandler(object):
    '''
    A custom Exception handler defining a method to react on errors
    '''
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
    The base class for all freedm module exceptions.
    '''
    # A template string or function for string representations of this exception
    template: Union[str, Callable] = None
    
    # A flag causing the program to halt when fatal is True
    fatal: bool = False
    
    # Logger
    logger = None
        
    def __init__(self, error) -> None:
        super().__init__(error)
        
        if not logger: self.logger = logging.getLogger()
        
        try:
            # Log message
            if isinstance(self.template, str):
                self.logger.error(self.template.format(error=error), exc_info=self.logger.level == logging.DEBUG)
            elif hasattr(self.template, '__call__'):
                self.logger.error(self.template(error), exc_info=self.logger.level == logging.DEBUG)
        except Exception as e:
            self.logger.error(f'Error when handling free.dm exception "{error.__class__.__name__}" ({e})')
        finally:
            # Is this a fatal exception?
            if self.fatal is True: sys.exit()


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
    fatal = True
    def template(self, error: Type[Exception]) -> str:
        if error.name:
            return(f'Missing module dependency ({error.name}): Please install via "pip install {error.name}"')
        else:
            return(f'Missing module dependency ({error})')