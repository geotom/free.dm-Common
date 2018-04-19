'''
This module defines a base transport node, participating in a
non server/client communicating system. Subclass from
this class to create a custom transport node implementation.
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    import time
    import textwrap
    from typing import TypeVar, Any, Optional, Type
    
    # free.dm Imports
    from freedm.utils.async import BlockingContextManager
    from freedm.utils import logging
    from freedm.utils.async import getLoop
    from freedm.utils.types import TypeChecker as checker
    from freedm.transport.message import Message
    from freedm.transport.protocol import Protocol
    from freedm.transport.connection import Connection, ConnectionType, ConnectionPool
    from freedm.transport.exceptions import freedmMessageLimitOverrun
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


TN = TypeVar('TN', bound='TransportNode')


class TransportNode(BlockingContextManager):
    '''
    A generic transport node implementation a socket based transport between different similar nodes.
    It can be used as a contextmanager or as asyncio awaitable.
    This node provides basic functionality for receiving and sending messages and supports:
    - Ephemeral and persistent (long-living) connections
    - Setting a maximum connection limit
    - Limiting amount of data sent or received
    - Reading data at once or in chunks
    '''
    
    # The context (This server)
    _node: Any=None
    
    # A register for active node connections
    _connection_pool: ConnectionPool=None
    
    # A state flag
    _shutdown = False
    
    # An identifier name for this server (Used for logging purposes). By default set to the class-name
    name = None
    
    def __init__(
            self,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            limit: Optional[int]=None,
            chunksize: Optional[int]=None,
            max_connections: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol]=None
            ) -> None:
        
        self.logger     = logging.getLogger()
        self.loop       = loop or getLoop()
        self.limit      = limit
        self.chunksize  = chunksize
        self.mode       = mode
        self.protocol   = protocol
        
        if not self.name:
            self.name = self.__class__.__name__
        if not self._connection_pool:
            self._connection_pool = ConnectionPool()
        if checker.isInteger(max_connections):
            self._connection_pool.max = max_connections
    