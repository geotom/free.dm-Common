'''
This module defines an IPC server connection object
@author: Thomas Wanderer
'''

# Imports
from enum import Enum
from collections import namedtuple


class ConnectionPool(object):
#https://www.pythonsheets.com/notes/python-asyncio.html#simple-asyncio-connection-pool
    pass


class ConnectionType(Enum):
    TEXT_DATA = 1
    STREAM_DATA = 2

Connection = namedtuple('Connection', 
    '''
    socket
    pid
    uid
    gis
    client_address
    server_address
    reader
    writer
    mode
    '''
    )