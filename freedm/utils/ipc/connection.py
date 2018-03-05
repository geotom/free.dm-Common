'''
This module defines an IPC server connection object
@author: Thomas Wanderer
'''

# Imports
import time
from datetime import timedelta
from enum import Enum
from collections import namedtuple
from typing import Type, TypeVar, List

# free.dm Imports
from freedm.utils.exceptions import freedmBaseException


C = TypeVar('C', bound='Connection')


class ConnectionPool(set):
    '''
    A set of active client sessions
    '''
    
    _max = None
    @property
    def max(self):
        '''Maximum allowed connections'''
        return self._max
    @max.setter
    def max(self, amount: int):
        if amount > len(self):
            self._max = amount
        else:
            raise freedmConnectionPoolMax()
        
    def isFull(self) -> bool:
        '''
        Returns if this connection pool can still accept new connections
        '''
        return False if not self.max else self.max <= len(self)
    
    def getConnections(self) -> List[Type[C]]:
        '''
        Return active connections
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self]
    
    def getConnectionsByAddress(self, address: str) -> List[Type[C]]:
        '''
        Return active connections from the specified address
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c.client_address == address]
    
    def getConnectionsByUser(self, uid: int) -> List[Type[C]]:
        '''
        Return active connections from the specified user ID
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c.uid == uid]
    
    def getConnectionsByGroup(self, gid: int) -> List[Type[C]]:
        '''
        Return active connections from the specified group ID
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c.gid == gid]
    
    def getConnectionsByProcess(self, pid: int) -> List[Type[C]]:
        '''
        Return active connections from the specified process ID
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c.pid == pid]

    def getIdleConnectionsSince(self, period: int) -> List[Type[C]]:
        '''
        Return active connections idling longer then the specified period in seconds
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if period <= timedelta(seconds=float(time.time() - c.state['update']))]
                
                
class ConnectionType(Enum):
    EPHEMERAL  = 1
    PERSISTENT = 2


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
    state
    '''
    )


class freedmConnectionPoolMax(freedmBaseException):
    '''
    Gets thrown when the maximum number of connections cannot be set on the connection pool
    '''
    template = 'Cannot set number of maximum connections lower than currently active session'