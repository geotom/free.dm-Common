'''
This module defines transport related object like connections and pools
@author: Thomas Wanderer
'''

# Imports
import time
from datetime import timedelta
from enum import Enum
from collections import namedtuple
from asyncio import Task
from typing import Type, TypeVar, List

# free.dm Imports
from freedm.utils.exceptions import freedmBaseException


C = TypeVar('C', bound='Connection')


class AddressType(Enum):
    DUAL = 1
    IPV4 = 2
    IPV6 = 3
    AUTO = 4


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
    
    def getConnections(self) -> List[C]:
        '''
        Return active connections
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c._coro.cr_frame]
    
    def getConnectionForHandler(self, handler: Task) -> List[C]:
        '''
        Return the connection for a specific connection handler
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if handler is c and c._coro.cr_frame][0]
    
    def getConnectionsByAddress(self, address: str) -> List[C]:
        '''
        Return active connections from the specified address
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c.peer_address == address and c._coro.cr_frame]
    
    def getConnectionsByUser(self, uid: int) -> List[C]:
        '''
        Return active connections from the specified user ID
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c.uid == uid and c._coro.cr_frame]
    
    def getConnectionsByGroup(self, gid: int) -> List[C]:
        '''
        Return active connections from the specified group ID
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c.gid == gid and c._coro.cr_frame]
    
    def getConnectionsByProcess(self, pid: int) -> List[C]:
        '''
        Return active connections from the specified process ID
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if c.pid == pid and c._coro.cr_frame]

    def getIdleConnectionsSince(self, period: int) -> List[C]:
        '''
        Return active connections idling longer then the specified period in seconds
        '''
        return [c._coro.cr_frame.f_locals['connection'] for c in self if period <= timedelta(seconds=float(time.time() - c.state['update'])) and c._coro.cr_frame]
                
                
class ConnectionType(Enum):
    EPHEMERAL  = 1
    PERSISTENT = 2


Connection = namedtuple('Connection', 
    '''
    socket
    sslctx
    sslobj
    pid
    uid
    gid
    peer_cert
    peer_address
    host_address
    reader
    writer
    read_handlers
    write_handlers
    state
    '''
    )


class freedmConnectionPoolMax(freedmBaseException):
    '''
    Gets thrown when the maximum number of connections cannot be set on the connection pool
    '''
    template = 'Cannot set number of maximum connections lower than currently active session'