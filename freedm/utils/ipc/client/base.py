'''
This module defines the base IPC server. 
Subclass from this class to create a custom IPC server implementation.
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    import time
    from typing import TypeVar, Optional, Type, Union
    
    # free.dm Imports
    from freedm.utils import logging
    from freedm.utils.async import getLoop
    from freedm.utils.ipc.protocol import Protocol
    from freedm.utils.ipc.message import Message
    from freedm.utils.ipc.connection import Connection, ConnectionType
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


IC = TypeVar('IC', bound='IPCSocketClient')


class IPCSocketClient(object):
    '''
    A generic client implementation to connect to IPC servers. It can be used 
    as a contextmanager or as asyncio awaitable. It supports basic message 
    exchange and can be configured with a protocol for advanced IPC communication.
    A client can:
    - Establish ephemeral and persistent (long-living) connections
    - Read data at once or in chunks
    '''
    
    # The context (This client)
    _context: IC=None
    
    # Reader and Writer
    _connection: Connection
    
    # Handler coroutine
    _handler: asyncio.coroutine=None
    
    def __init__(
            self,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            limit: Optional[int]=None,
            chunksize: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol] = None
            ) -> None:
        
        self.logger = logging.getLogger()
        self.loop = loop or getLoop()
        self.limit = limit
        self.chunksize = chunksize
        self.mode = mode
        self.protocol = protocol
        
    async def __aenter__(self) -> IC:
        '''
        A template function that should be implemented by any subclass
        '''
        return self
        
    async def __aexit__(self) -> None:
        '''
        Cancel the connection and close the socket
        '''
        pass
    
    async def __await__(self) -> IC:
        '''
        Makes this class awaitable
        '''
        return await self.__aenter__()
    
    def _assembleConnection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Connection:
        '''
        Assemble a connection object based on the info we get from the reader/writer
        '''
        return Connection(
            socket=writer.get_extra_info('socket'),
            pid=None,
            uid=None,
            gid=None,
            client_address=None,
            server_address=None,
            reader=reader,
            writer=writer,
            state={
                'mode': self.mode or ConnectionType.PERSISTENT,
                'creation': time.time(),
                'update': time.time()
                }
            )
    
    async def handleConnection(self, connection: Connection) -> None:
        '''
        Handle the connection and listen for incoming messages until we receive an EOF.
        '''
        pass
    
    async def handleMessage(self, message):
        '''
        A template function that should be overwritten by any subclass if required
        '''
        self.logger.debug(f'IPC server received: {message.data.decode()}')
        await self.sendMessage('Pong' if message.data.decode() == 'Ping' else message.data.decode(), message.sender)
        