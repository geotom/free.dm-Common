'''
General Logging utilities. Please use this logging facility throughout free.dm packages.
@author: Thomas Wanderer
'''

# Imports
import os
import logging
from typing import Type, Optional, Union

# free.dm Imports
from freedm.defaults import constants

# Set logging module
logging = logging

# Constants
CRITICAL = logging.CRITICAL
FATAL = logging.CRITICAL
ERROR = logging.ERROR
WARNING = logging.WARN
WARN = logging.WARN
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

# Colors
logging.addLevelName(logging.WARNING, f'\033[1;33m{logging.getLevelName(logging.WARNING)}\033[1;0m ')
logging.addLevelName(logging.ERROR, f'\033[1;31m{logging.getLevelName(logging.ERROR)}\033[1;0m   ')
logging.addLevelName(logging.CRITICAL, f'\033[1;41m{logging.getLevelName(logging.CRITICAL)}\033[1;0m')
logging.addLevelName(logging.INFO, f'\033[1;32m{logging.getLevelName(logging.INFO)}\033[1;0m    ')

# Formats
FORMAT_DEFAULT = '%(asctime)s %(levelname)-8s %(message)s'
FORMAT_DATE = '%d.%m.%Y %H:%M:%S'
FORMAT_DEBUG = '%(asctime)s %(levelname)-8s %(message)s [%(module)s.%(funcName)s():#%(lineno)s]'


def getLevelName(level: int) -> str:
    '''
    Return the current log-level name
    '''
    return logging.getLevelName(level)


def setFormat(name: Optional[Union[int, str]]=None, fmt: str=None, datefmt: str=None) -> None:
    '''
    Set a new logger format on all logger handlers
    '''
    if name is None:
        name = os.getpid()
    logger = getLogger(name)
    formatter = logging.Formatter(fmt if fmt else (FORMAT_DEBUG if logger.level == logging.DEBUG else FORMAT_DEFAULT), datefmt if datefmt else FORMAT_DATE)
    for handler in logger.handlers:
        handler.setFormatter(formatter)
    logger.debug(f'Updated logger "{name}" format')


def getLogger(name: Optional[Union[int, str]]=None, level: Optional[int]=None, handler: Optional[Type[logging.Handler]]=None) -> Type[logging.Logger]:
    '''
    Sets up the Python logging facility with the according integer loglevel
    '''

    # Get level or set default (In DEBUG mode, we do not respect any provided level)
    if constants.MODE == 'debug':
        level = logging.DEBUG
    elif level:
        level = int(level)

    # Define logger format
    formatter = logging.Formatter(FORMAT_DEBUG if level == logging.DEBUG else FORMAT_DEFAULT, FORMAT_DATE)

    # Get logger name
    if name is None:
        name = os.getpid()
    name = str(name)

    # Get the logger
    try:
        if name in getattr(logging.Logger, 'manager').loggerDict.keys():
            # Use already existing handler and update level if needed
            logger = logging.getLogger(name=name)
            # Update the log level/handlers if required
            if level and logger.level != level:
                logger.setLevel(level)
                logger.debug(f'Changed log level of logger "{name}" to "{getLevelName(level)}"')
            # Update format
            if level:
                for handler in logger.handlers:
                    if handler.formatter._fmt != formatter._fmt:
                        handler.setFormatter(formatter)
        else:
            # Create new logger via logging factory
            logger = logging.getLogger(name=name)
            logger.setLevel(level or logging.DEBUG)
            handler = handler or logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.debug(f'Setup logger "{name}" set up with log level "{getLevelName(level or logging.DEBUG)}"')
    except Exception:
        logger = logging.getLogger(name)

    # Return logger
    return logger


class EventHandler(logging.Handler):
    '''
    A custom handler class that emits each log entry as event
    '''

    def emit(self, record: Type[logging.LogRecord]) -> None:
        print('EVENT EMITTER', record.getMessage())
