'''
This module defines the base IPC server. 
Subclass from this class to create a custom IPC server implementation.
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    import signal
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
    
    # The context (This connection)
    _connection: Connection=None
    
    # Handler coroutine
    _handler: asyncio.coroutine=None
    
    def __init__(
            self,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            timeout: int=None,
            limit: Optional[int]=None,
            chunksize: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol] = None
            ) -> None:
        
        self.logger     = logging.getLogger()
        self.loop       = loop or getLoop()
        self.timeout    = timeout
        self.limit      = limit
        self.chunksize  = chunksize
        self.mode       = mode
        self.protocol   = protocol
        
    async def __aenter__(self) -> IC:
        '''
        A template function that should be implemented by any subclass
        '''
        self._connection = self._assembleConnection(reader=asyncio.StreamReader(), writer=asyncio.StreamWriter())
        self._handler = asyncio.ensure_future(self.handleConnection(self._connection))
        self._handler.add_done_callback(self.__aexit__)
        return self
        
    async def __aexit__(self) -> None:
        '''
        Cancel the connection and close the socket
        '''
        if self._handler:
            
            print('==> CANCELING HANDLER', self._handler)
            
            # Set internals to None again
            handler = self._handler
            connection = self._connection
            self._handler = None
            self._connection = None
            
            # Cancel the handler
            handler.cancel()
            
            # Close the connection
            await self.closeConnection(connection)
            

    async def __await__(self) -> IC:
        '''
        Makes this class awaitable
        '''
        return await self.__aenter__()
    
    def connected(self):
        return self._connection and self._connection.state['closed']
    
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
                'created': time.time(),
                'updated': time.time(),
                'closed': None
                }
            )
        
    async def closeConnection(self, connection):
        '''
        End and close an existing connection:
        Acknowledge or inform client about EOF, then close
        '''
        connection.state['closed'] = time.time()
        if not connection.writer.transport.is_closing():
            if connection.reader.at_eof():
                self.logger.debug('IPC connection closed by server')
                connection.reader.feed_eof()
            else:
                self.logger.debug('IPC connection closed by client')
                if connection.writer.can_write_eof(): connection.writer.write_eof()
            await asyncio.sleep(.1)
            connection.writer.close()
            self.logger.debug('IPC connection writer closed')
    
    async def handleConnection(self, connection: Connection) -> None:
        '''
        Handle the connection and listen for incoming messages until we receive an EOF.
        '''
        print('----------------------------')
        print('Handling the connection', connection)
        print('Timeout', self.timeout)
        print('----------------------------')
    
    async def handleMessage(self, message: Message):
        '''
        A template function that should be overwritten by any subclass if required
        '''
        
        NOCH AUF TIMEOUT ACHTEN
         
        LANGLEBIGE CLIENT CONNECTIONS müssen geschlossen werden können
        
        SOlLEN BEI WITH ASYNC gleich Connection auf Ephemeral gesetzt werden?
         
        Einen Incoming Listener implementieren
        
        Send message implementieren
        
        CONTEXT MANAGER MIT SIGNALS DIE AUF KEYBOARD INTERRUPTS ACHTEN
        https://stackoverflow.com/questions/842557/how-to-prevent-a-block-of-code-from-being-interrupted-by-keyboardinterrupt-in-py/21919644
        
        self.logger.debug(f'IPC server received: {message.data.decode()}')
        await self.sendMessage('Pong' if message.data.decode() == 'Ping' else message.data.decode(), message.sender)
    
    async def close(self) -> None:
        '''
        Stop this client connection
        '''
        await self.__aexit__()