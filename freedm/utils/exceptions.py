'''
A utility class for exception handling.
@author: Thomas Wanderer
'''

# Imports
import sys
import platform
import traceback
from typing import Union, Callable, Type, Optional

# free.dm Imports
from . import logging


class ExceptionHandler:
    '''
    A custom Exception handler defining a method to react on errors
    '''
    # Logger
    logger = None

    def __init__(self, handler: Optional[str]=None, logger: Optional[Type[logging.logging.Logger]]=None):
        # Set a logger
        self.__class__.logger = logger or logging.getLogger()

        # Get correct exception handler
        try:
            if not handler:
                handler = 'default'
            method = getattr(self.__class__, f'{handler.lower()}_handler')
            if not hasattr(method, '__call__'):
                method = self.defaultHandler
        except AttributeError:
            logger.error(f'Exception handler "{handler}" is not implemented')
            method = self.defaultHandler
        except Exception as e:
            logger.error(f'Cannot setup exception handler "{handler}" ({e})')
            method = self.defaultHandler

        # Finally set this as global exception handler
        finally:
            def exception_handler(error_type, error, error_trace):
                try:
                    method(error_type, error, error_trace)
                except Exception as e:
                    ExceptionHandler.logger.error(f'Cannot handle exception ({e})', exc_info=False)
                finally:
                    # Is this a fatal exception?
                    try:
                        fatal = error.fatal
                    except Exception:
                        fatal = False
                    if fatal:
                        sys.exit()
            previous = sys.excepthook.__name__
            sys.excepthook = exception_handler
            if previous == 'exception_handler':
                ExceptionHandler.logger.debug(f'Changed exception handler to "{method.__name__[:-8].upper()}"')
            else:
                ExceptionHandler.logger.debug(f'Setup exception handler "{method.__name__[:-8].upper()}"')

    @staticmethod
    def default_handler(error_type, error, error_trace) -> None:
        logger = ExceptionHandler.logger or logging.getLogger()
        logger.error(f'{error_type.__name__}: "{error}"')

    @staticmethod
    def product_handler(error_type, error, error_trace) -> None:
        logger = ExceptionHandler.logger or logging.getLogger()
        logger.error(f'Exception "{error_type.__name__}" occurred!')

    @staticmethod
    def debug_handler(error_type, error, error_trace) -> None:
        logger = ExceptionHandler.logger or logging.getLogger()
        try:
            logger.error(error, exc_info=False)
        except Exception as e:
            logger.error(f'Error when handling exception "{error_type.__name__}" ({e})')
        finally:
            if logger.level == logging.DEBUG:
                # sys.__excepthook__(error_type, error, error_trace)
                traceback.print_exception(None, error, error_trace, chain=True)


class freedmBaseException(Exception):
    '''
    The base class for all freedm module exceptions.
    '''
    # A template string or function for string representations of this exception
    template: Union[str, Callable] = None

    # A flag causing the program to halt when fatal is True
    fatal: bool = False

    def __init__(self, error) -> None:
        super().__init__(error)
        try:
            if isinstance(self.template, str):
                self.message = self.template.format(error=error)
            elif hasattr(self.template, '__call__'):
                self.message = self.template(error)
            else:
                self.message = error
        except Exception as e:
            self.message = f'Error when building exception "{error.__class__.__name__}" message ({e})'


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
