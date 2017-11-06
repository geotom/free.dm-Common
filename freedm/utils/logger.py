'''
General Logging utilities. Please use this logging facility throughout free.dm packages. 
@author: Thomas Wanderer
'''

# Imports
import logging
from typing import Type

# free.dm Imports
from freedm.utils import globals as G

def getLogger(pid: int=None, level: int=None):
    '''
    Sets up the Python logging facility with the according integer loglevel
    :param int: The process ID (PID)
    :param int: The system loglevel (10, 20, 30, 40, 50). In debug Mode always 10 (=logging.DEBUG)
    '''
    
    # Get level or set default (In DEBUG mode, we do not respect any provided level)
    if level is None:
        level = logging.DEBUG
    if G.MODE == 'debug': 
        level = logging.DEBUG
    else:
        level = int(level)
    
    # Get level or set default
    if pid is None:
        import os
        pid = os.getpid()
        
    # Setup formatting
    if G.MODE == 'debug':
        logging.basicConfig(
            format='%(asctime)s %(levelname)-8s %(message)s [%(module)s.%(funcName)s():#%(lineno)s]',
            datefmt='%d.%m.%Y %H:%M:%S',
            level=level
            )
    else:
        logging.basicConfig(
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%d.%m.%Y %H:%M:%S',
            level=level
            )
    
    # Define & return a logger with the process PID
    try:
        if str(pid) in getattr(logging.Logger, 'manager').loggerDict.keys():
            return logging.getLogger(str(pid))
        else:
            # Create new logger via logging factory
            logger = logging.getLogger(str(pid))   
            # Add event emitting handler
            logger.addHandler(EventHandler())
            # Log the setup completion
            logger.debug(f'Logging facility set up with log level "{logging.getLevelName(level)}"')
            # Return the logger
            return logger
    except:
        return logging.getLogger(str(pid))

class EventHandler(logging.Handler):
    '''
    A custom handler class used in debug mode providing more output
    '''
    
    def __init__(self):
        logging.Handler.__init__(self)
        self.setLevel(logging.INFO)
        
    def emit(self, record: Type[logging.LogRecord]) -> None:
        #print('EVENT EMITTER', record.getMessage())
        pass
