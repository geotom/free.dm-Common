'''
This module defines the base IPC server. 
Subclass from this class to create a custom IPC server implementation.
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    import time
    from typing import Union, Type, Optional, Set, TypeVar, Iterable
    
    # free.dm Imports
    from freedm.utils.async import getLoop
    from freedm.utils.types import TypeChecker as checker
    from freedm.utils.exceptions import freedmBaseException
    from freedm.utils.ipc.message import Message
    from freedm.utils.ipc.connection import Connection, ConnectionType, ConnectionPool
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


IS = TypeVar('IS', bound='IPCSocketServer')


class IPCSocketServer(object):
    '''
    A generic server implementation for IPC servers allowing to communicate with connected clients
    while keeping a list of active connections. It can be used as a contexmanager or as asyncio awaitable.
    This IPC server provides basic functionality for receiving and sending messages and supports:
    - Ephemeral and persistent (long-living) connections
    - Setting a maximum connection limit
    - Limiting amount of data sent or received
    - Reading data at once or in chunks
    - Client authentication
    '''
    
    # The context (This server)
    _context: IS=None
    
    # A register for active client connections
    _connection_pool: ConnectionPool=None
    
    def __init__(
            self,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            limit: Optional[int]=None,
            chunksize: Optional[int]=None,
            max_connections: Optional[int]=None,
            mode: Optional[Union[ConnectionType]]=None
            ) -> None:
        
        self.loop = loop or getLoop()
        self.limit = limit
        self.chunksize = chunksize
        self.mode = mode
        
        if not self._connection_pool:
            self._connection_pool = ConnectionPool()
        if checker.isInteger(max_connections):
            self._connection_pool.max = max_connections
        
    async def __aenter__(self) -> IS:
        '''
        A template function that should be implemented by any subclass
        '''
        return self
        
    async def __aexit__(self) -> None:
        '''
        Cancel all pending connections in the connection pool
        '''
        for c in self._connection_pool:
            c.cancel()
        
    async def __await__(self) -> IS:
        '''
        Makes this class awaitable
        '''
        return await self.__aenter__()
    
    def _assembleConnection(self, reader: Type[asyncio.StreamReader], writer: Type[asyncio.StreamWriter]) -> Optional[Connection]:
        '''
        Assemble a connection object based on the info we get from the reader/writer
        '''
        return Connection(
            socket=writer.get_extra_info('socket'),
            pid=None,
            uid=None,
            gis=None,
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
    
    def _onConnectionEstablished(self, reader: Type[asyncio.StreamReader], writer: Type[asyncio.StreamWriter]) -> asyncio.Task:
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
            session = asyncio.ensure_future(self.handleConnection(connection))
            self._connection_pool.add(session)
            session.add_done_callback(lambda task: self._connection_pool.remove(session))
        return session
    
    async def rejectConnection(self, connection: Connection, reason: Optional[str]=None) -> None:
        '''
        A template function for rejecting a connection attempt
        '''
        print(f'-> Rejecting connection ({reason})')
        if reason: await self.sendMessage(reason, connection)
        await self.closeConnection(connection)
        
    
    async def closeConnection(self, connection):
        '''
        End and close an existing connection
        '''
        # Acknowledge or inform client about EOF, then close
        if not connection.writer.transport.is_closing():
            if connection.reader.at_eof():
                print('CLOSING BY Client')
                connection.reader.feed_eof()
            else:
                print('CLOSING BY SERVER')
                if connection.writer.can_write_eof(): connection.writer.write_eof()
            await asyncio.sleep(.1)
            connection.writer.close()
            print('WRITER CLOSED!!!')
    
    async def handleConnection(self, connection: Connection) -> None:
        '''
        Handle the connection and listen for incoming messages until we receive an EOF.
        '''
        # Authenticate
        auth = await self.authenticateConnection(connection)
        if auth:
            print('-> Connection was successfully authenticated')
        else:
            await self.rejectConnection(connection, 'Could not authenticate')
            return
        
        # Read data depending on the connection type and handle it
        chunks = 0
        while not connection.reader.at_eof():
            # Read up to the limit or as many chunks until the limit
            try:
                if self.chunksize:
                    if self.limit and self.limit - chunks*self.chunksize < self.chunksize:
                        break
                    raw = await connection.reader.read(self.chunksize)
                    chunks += 1
                else:
                    raw = await connection.reader.read(self.limit or -1)
            except Exception as e:
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
                    raise freedmIPCMessageHandler(e)
        
        # Close the connection (It will be automatically removed rom the pool)
        await self.closeConnection(connection)
            
    async def authenticateConnection(self, connection: Type[Connection]) -> bool:
        '''
        A template function that should be overwritten by any subclass if required
        '''
        return True
    
    async def handleMessage(self, message):
        '''
        A template function that should be overwritten by any subclass if required
        '''
        print('Received:', message.data.decode())
        await self.sendMessage('Pong' if message.data.decode() == 'Ping' else message.data.decode(), message.sender)
        
    async def sendMessage(self, message: Union[str, int, float], connection: Union[Type[Connection], Iterable[Type[Connection]]]=None) -> None:
        '''
        Send a message to either one or more connections
        '''
        for c in [[connection] if not checker.isIterable(connection) else connection]:
            # Write message to socket if size is met and connection not closed
            try:
                message = str(message).encode()
                if len(message) == 0:
                    return
                if self.limit and len(message) > self.limit:
                    raise freedmIPCMessageLimitOverrun()
                if not c.writer.transport.is_closing():
                    c.writer.write(message)
                    await c.writer.drain()
            except Exception as e:
                raise freedmIPCMessageWriter(e)
            
            # In case this is an ephemeral connection, close it immediately after sending this message
            if c.state['mode'] == ConnectionType.EPHEMERAL:
                await self.closeConnection(c)
    
    async def close(self) -> None:
        '''
        Shutdown this server
        '''
        await self.__aexit__()


class freedmIPCSocketCreation(freedmBaseException):
    '''
    Gets thrown when the IPC socket module cannot create a socket
    '''
    template = 'Cannot create IPC socket ({error})'
    

class freedmIPCMessageWriter(freedmBaseException):
    '''
    Gets thrown when the IPC socket module cannot send a message
    '''
    template = 'Cannot write message to IPC socket ({error})'
    

class freedmIPCMessageReader(freedmBaseException):
    '''
    Gets thrown when the IPC socket module cannot read and message
    '''
    template = 'Cannot read message from IPC socket ({error})'
    
    
class freedmIPCMessageHandler(freedmBaseException):
    '''
    Gets thrown when the IPC message handler creates an exception
    '''
    template = 'IPC Message handler failed ({error})'
    
    
class freedmIPCMessageLimitOverrun(freedmBaseException):
    '''
    Gets thrown when the IPC socket receives/sends a message exceeding the limit set
    '''
    template = 'IPC Message length exceeds limit set ({error})'