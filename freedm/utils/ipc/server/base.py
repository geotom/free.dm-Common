'''
This module defines the base IPC server. 
Subclass from this class to create a custom IPC server implementation.
@author: Thomas Wanderer
'''
from mypy.types import Instance

try:
    # Imports
    import asyncio
    import time
    from typing import Union, Type, Optional, Set, TypeVar, Iterable, Any
    
    # free.dm Imports
    from freedm.utils.async import BlockingContextManager
    from freedm.utils import logging
    from freedm.utils.async import getLoop
    from freedm.utils.types import TypeChecker as checker
    from freedm.utils.ipc.message import Message
    from freedm.utils.ipc.protocol import Protocol
    from freedm.utils.ipc.connection import Connection, ConnectionType, ConnectionPool
    from freedm.utils.ipc.exceptions import freedmIPCMessageReader, freedmIPCMessageHandler, freedmIPCMessageLimitOverrun, freedmIPCMessageWriter
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


IS = TypeVar('IS', bound='IPCSocketServer')


class IPCSocketServer(BlockingContextManager):
    '''
    A generic server implementation for IPC servers allowing to communicate with connected clients
    while keeping a list of active connections. It can be used as a contextmanager or as asyncio awaitable.
    This IPC server provides basic functionality for receiving and sending messages and supports:
    - Ephemeral and persistent (long-living) connections
    - Setting a maximum connection limit
    - Limiting amount of data sent or received
    - Reading data at once or in chunks
    - Client authentication
    '''
    
    # The context (This server)
    _server: Type[asyncio.AbstractServer]=None
    
    # A register for active client connections
    _connection_pool: ConnectionPool=None
    
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
        
        if not self._connection_pool:
            self._connection_pool = ConnectionPool()
        if checker.isInteger(max_connections):
            self._connection_pool.max = max_connections
        
    async def __aenter__(self) -> IS:
        '''
        A template function that should be implemented by any subclass
        '''
        # Call parent (Required to profit from SaveContextManager)
        await super().__aenter__()
        
        # Initialize and create a server a server
        self._server = await self._init_server()

        # Check & Return self
        if not self._server: self.logger('IPC server could not be started')
        return self
        
    async def __aexit__(self) -> None:
        '''
        Cancel all pending connections in the connection pool
        '''
        # Call pre-shutdown procedure
        await self._pre_shutdown()
        
        # Cancel active connection handlers
        for connection in self._connection_pool:
            connection.cancel()
            
        # TODO: Should we also cancel active sendMessage coroutines?
        
        # Inform active clients of exit
        try:
            asyncio.wait(
                [await self.closeConnection(c) for c in self._connection_pool.getConnections()],
                timeout=3,
                loop=self.loop
                )
        except:
            pass
        
        # Close the server
        try:
            self._server.close()
        except Exception as e:
            self.logger.error('Cannot close IPC UXD socket server', self._server, e)
        try:   
            await self._server.wait_closed()
        except Exception as e:
            self.logger.error('Could not wait until IPC UXD server closed', self._server, e)    
        
        # Call post-shutdown procedure
        await self._post_shutdown()
            
        # Call parent (Required to profit from SaveContextManager)
        await super().__aexit__()
    
    async def __await__(self) -> IS:
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
                'created': time.time(),
                'updated': time.time(),
                'closed': None
                }
            )
    
    def _onConnectionEstablished(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> asyncio.Task:
        '''
        Responsible for the creation and recycling of connections for any new established session
        and subsequently hands over the further session handling
        '''
        # Build a connection object
        connection = self._assembleConnection(reader, writer)
        
        # Check if max connection is not exceeded?
        if self._connection_pool.isFull():
            session = asyncio.ensure_future(self.rejectConnection(connection, 'Too many connections'))
        else:
            session = asyncio.ensure_future(self._handleConnection(connection), loop=self.loop)
            self._connection_pool.add(session)
            session.add_done_callback(lambda task: self._connection_pool.remove(session))
        return session
    
    async def rejectConnection(self, connection: Connection, reason: Optional[str]=None) -> None:
        '''
        A template function for rejecting a connection attempt
        '''
        self.logger.debug(f'-> Rejecting connection ({reason})')
        if reason: await self.sendMessage(reason, connection)
        await self.closeConnection(connection)
        
    async def closeConnection(self, connection: Connection) -> None:
        '''
        End and close an existing connection:
        Acknowledge or inform client about EOF, then close
        '''
        connection.state['closed'] = time.time()
        if not connection.writer.transport.is_closing():
            if connection.reader.at_eof():
                self.logger.debug('IPC connection closed by client')
                connection.reader.feed_eof()
            else:
                self.logger.debug('IPC connection closed by server')
                if connection.writer.can_write_eof(): connection.writer.write_eof()
            await asyncio.sleep(.1)
            connection.writer.close()
            self.logger.debug('IPC connection writer closed')
            
    async def _init_server(self) -> Any:
        '''
        Template function for initializing the server.
        It should start a server and return it
        '''
        return
        
    async def _pre_shutdown(self) -> None:
        '''
        Template function to prepare the shutdown of the server
        before we cancel all current connections, signal the shutdown to
        connected clients and clos the server object
        '''
        return
    
    async def _post_shutdown(self) -> None:
        '''
        Template function to clean up after the server has
        been shutdown
        '''
        return
    
    async def _handleConnection(self, connection: Connection) -> None:
        '''
        Handle the connection and listen for incoming messages until we receive an EOF.
        '''
        # Authenticate
        auth = await self.authenticateConnection(connection)
        if auth:
            self.logger.debug('IPC connection was successfully authenticated')
        else:
            await self.rejectConnection(connection, 'Could not authenticate')
            return
        
        # Read data depending on the connection type and handle it
        chunks = 0
        while not connection.reader.at_eof():
            # Update the connection
            connection.state['updated'] = time.time()
            # Read up to the limit or as many chunks until the limit
            try:
                if self.chunksize:
                    if self.limit and self.limit - chunks * self.chunksize < self.chunksize:
                        break
                    raw = await connection.reader.read(self.chunksize)
                    chunks += 1
                else:
                    raw = await connection.reader.read(self.limit or -1)
            except asyncio.CancelledError:
                # We exit and can return as the connection closing is handled in __aexit__
                return
            except Exception as e:
                # TODO: Don't raise an error or self.closeConnection
                await self.closeConnection(connection)
                raise freedmIPCMessageReader(e)
            # Handle the received message or message fragment
            if not len(raw) == 0:
                message = Message(
                    data=raw,
                    sender=connection
                    )
                try:
                    await self.handleMessage(message)
                except Exception as e:
                    # TODO: Don't raise an error or self.closeConnection
                    # self.closeConnection(connection)
                    raise freedmIPCMessageHandler(e)
        
        # Close the connection (It will be automatically removed from the pool)
        await self.closeConnection(connection)
            
    async def authenticateConnection(self, connection: Connection) -> bool:
        '''
        A template function that should be overwritten by any subclass if required
        '''
        return True
    
    async def handleMessage(self, message: Message):
        '''
        A template function that should be overwritten by any subclass if required
        '''
        self.logger.debug(f'IPC server received: {message.data.decode()}')
        await self.sendMessage('Pong' if message.data.decode() == 'Ping' else message.data.decode(), message.sender)
        
    async def sendMessage(self, message: Union[str, int, float], connection: Union[Connection, Iterable[Connection]]=None) -> bool:
        '''
        Send a message to either one or more connections
        '''
        try:
            # Get affected connections
            connections = [connection] if not checker.isIterable(connection) else connection
    
            # Encode and check message
            message = str(message).encode()
            if len(message) == 0:
                return
            if self.limit and len(message) > self.limit:
                raise freedmIPCMessageLimitOverrun()
            
            # Dispatch message to affected connections
            if len(connections) > 0:                
                dispatch_report = await asyncio.gather(
                    *[self._dispatchMessage(message, c) for c in connections],
                    loop=self.loop,
                    return_exceptions=True
                    )
                return all(not isinstance(success, Exception) for success in dispatch_report)
        except asyncio.CancelledError:
            pass
        
    async def _dispatchMessage(self, message: bytes, connection: Connection) -> bool:
        try:
            if not connection.writer.transport.is_closing():
                # Dispatch message
                connection.writer.write(message)
                await connection.writer.drain()
                # Close an ephemeral connection, immediately after sending the message
                if connection.state['mode'] == ConnectionType.EPHEMERAL:
                    await self.closeConnection(connection)
                # Return result
                return True
            else:
                raise freedmIPCMessageWriter(e)   
        except asyncio.CancelledError:
            return
        except Exception as e:
            raise freedmIPCMessageWriter(e)
    
    async def close(self) -> None:
        '''
        Stop this server
        '''
        await self.__aexit__()