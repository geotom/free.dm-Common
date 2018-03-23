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
    from freedm.utils.async import BlockingContextManager
    from freedm.utils import logging
    from freedm.utils.async import getLoop
    from freedm.utils.ipc.protocol import Protocol
    from freedm.utils.ipc.message import Message
    from freedm.utils.ipc.connection import Connection, ConnectionType
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


IC = TypeVar('IC', bound='IPCSocketClient')


class IPCSocketClient(BlockingContextManager):
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
        # Call parent (Required to profit from SaveContextManager)
        await super().__aenter__()
        return self
        
    async def __aexit__(self) -> None:
        '''
        Cancel the connection handler and close the connection
        '''
        # Set internals to None again
        handler = self._handler
        connection = self._connection
        self._handler = None
        self._connection = None
             
        # Call pre-shutdown preparation
        try:
            await self._pre_disconnect(connection)
        except Exception as e:
            self.logger.error(f'IPC connection pre-shutdown failed with error ({e})')
        
        # Cancel the handler  
        if handler:
            handler.cancel()
            
        # Close the connection
        if connection:
            await self.closeConnection(connection)
            
        # Call post shutdown cleanup
        try:
            await self._post_disconnect(connection)
        except Exception as e:
            self.logger.error(f'IPC connection pre-shutdown failed with error ({e})')
            
        # Call parent (Required to profit from SaveContextManager)
        await super().__aexit__()

    async def __await__(self) -> IC:
        '''
        Makes this class awaitable
        '''
        return await self.__aenter__()
    
    def connected(self):
        '''
        Checks if the connection is still alive
        '''
        return self._connection and not self._connection.state['closed']
    
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
        if not connection.writer.transport.is_closing():
            print('CLOSING CONECTION!!!')
            try:
                if connection.reader.at_eof():
                    self.logger.debug('IPC connection closed by server')
                    connection.reader.feed_eof()
                else:
                    self.logger.debug('IPC connection closed by client')
                    if connection.writer.can_write_eof(): connection.writer.write_eof()
                await asyncio.sleep(.1)
                connection.writer.close()
            except:
                pass
            finally:
                connection.state['closed'] = time.time()
                self.logger.debug('IPC connection writer closed')
                
    async def _onConnectionEstablished(self, connection: Connection) -> None:
        '''
        This function calls the connection handler and ensures its closing when a timeout is set
        '''
        self._connection = connection
        self._handler = asyncio.ensure_future(self._handleConnection(self._connection), loop=self.loop)
        # Stop the connection handler after a specified timeout
        if self.timeout:
            await asyncio.sleep(self.timeout)
            if not self._handler.done():
                self._handler.cancel()
                await self.close()
                self.logger.debug(f'IPC connection stopped after timeout of {self.timeout} seconds')
                
    async def _pre_disconnect(self, connection: Connection) -> None:
        '''
        Template function to prepare the closing of the connection
        before we call closeConnection(__aexit__)
        '''
        return
    
    async def _post_disconnect(self, connection: Connection) -> None:
        '''
        Template function to cleanup after the closing of the connection
        via closeConnection(__aexit__)
        '''
        return
    
    async def _handleConnection(self, connection: Connection) -> None:
        '''
        Handle the connection and listen for incoming messages until we receive an EOF.
        '''
        try:
#             print('----------------------------')
#             print('Handling the connection', connection)
#             print('Timeout', self.timeout)
#             print('----------------------------')
            while True:
                print('...handling Connection')
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print('I, THE HANDLER GOT CANCELED !!!')
            #return
        except:
            return
    
    async def handleMessage(self, message: Message):
        '''
        A template function that should be overwritten by any subclass if required
        '''
        
#         NOCH AUF TIMEOUT ACHTEN
#          
#         LANGLEBIGE CLIENT CONNECTIONS müssen geschlossen werden können
#         
#         SOlLEN BEI WITH ASYNC gleich Connection auf Ephemeral gesetzt werden?
#          
#         Einen Incoming Listener implementieren
#         
#         Send message implementieren
#         
#         CONTEXT MANAGER MIT SIGNALS DIE AUF KEYBOARD INTERRUPTS ACHTEN
#         https://stackoverflow.com/questions/842557/how-to-prevent-a-block-of-code-from-being-interrupted-by-keyboardinterrupt-in-py/21919644
#         https://www.python.org/dev/peps/pep-0419/
        
        self.logger.debug(f'IPC server received: {message.data.decode()}')
        await self.sendMessage('Pong' if message.data.decode() == 'Ping' else message.data.decode(), message.sender)
    
    async def close(self) -> None:
        '''
        Stop this client connection
        '''
        await self.__aexit__()