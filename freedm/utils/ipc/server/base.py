'''
This module defines the base IPC server. 
Subclass from this class to create a custom IPC server implementation.
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    import time
    import functools
    from typing import Union, Type, Optional, TypeVar, Iterable, Any
    
    # free.dm Imports
    from freedm.utils.async import BlockingContextManager
    from freedm.utils import logging
    from freedm.utils.async import getLoop
    from freedm.utils.types import TypeChecker as checker
    from freedm.utils.ipc.message import Message
    from freedm.utils.ipc.protocol import Protocol
    from freedm.utils.ipc.connection import Connection, ConnectionType, ConnectionPool
    from freedm.utils.ipc.exceptions import freedmIPCMessageLimitOverrun, freedmIPCMessageWriter
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
    
    # A state flag
    _shutdown = False
    
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
        
    async def __aexit__(self, *args) -> None:
        '''
        Cancel all pending connections in the connection pool
        '''
        # Set shutdown flag
        self._shutdown = True
        
        # Call pre-shutdown procedure
        await self._pre_shutdown()
        
        # Cancel active connection handlers
        for connection in self._connection_pool:
            connection.cancel()
            
        # Inform active clients of shutdown and cancel their active read/write handlers
        try:
            connections = self._connection_pool.getConnections()
            asyncio.wait(
                [await self.closeConnection(c) for c in connections],
                timeout=None,
                loop=self.loop
                )
        
            async def cancel_connection_handlers(connection: Connection) -> None:
                for reader in connection.read_handlers:
                    try:
                        if not reader.done():
                            print('CANCELING CONECTIONR READER')
                            reader.cancel()
                    except Exception as e:
                        print('READER ERROR', e)
                for writer in connection.write_handlers:
                    try:
                        if not writer.done():
                            print('CANCELING CONNECTION WRITER')
                            writer.cancel()
                        else:
                            print('IST DOCH SCHON GECANCELD ??? !!!')
                    except Exception as e:
                        print('WRITER ERROR', e)
            
            print('==> ClOSING NOW CONNECTION Read/Write HANDLERS')
            
            asyncio.wait(
                [await cancel_connection_handlers(c) for c in connections],
                timeout=None,
                loop=self.loop
                )
                
            print('==> CANCELATION DONE')
        except Exception as e:
            print('==> CANCELATION ERROR:',e)
        
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
            read_handlers=set(),
            write_handlers=set(),
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
        try:
            # Authenticate
            auth = await self.authenticateConnection(connection)
            if auth:
                self.logger.debug('IPC connection was successfully authenticated')
            else:
                await self.rejectConnection(connection, 'Could not authenticate')
                return
                        
            # Read data depending on the connection type and handle it
            chunks = 0
            chunksize = self.chunksize
            while not connection.reader.at_eof():
                try:
                    # Update the connection
                    connection.state['updated'] = time.time()
                    
                    # Read up to the limit or as many chunks until the limit
                    if self.chunksize:
                        # Make sure we read as many chunks till reaching the limit
                        if self.limit:
                            chunksize = min(self.limit, self.chunksize)
                            consumed = chunks * self.chunksize
                            rest = self.limit - consumed
                            if self.limit == chunksize and chunks > 0:
                                break
                            if rest <= 0:
                                break
                            chunksize = chunksize if rest > chunksize else rest
                        raw = await connection.reader.read(chunksize)
                        chunks += 1
                    else:
                        raw = await connection.reader.read(self.limit or -1)
                    
                    # Handle the received message or message fragment
                    if not len(raw) == 0:
                        message = Message(
                            data=raw,
                            sender=connection
                            )
                        # Never launch another message handler while we're being shutdown (this task getting cancelled)
                        if not self._shutdown:
                            reader = asyncio.ensure_future(self.handleMessage(message))
                            reader.add_done_callback(lambda task: connection.read_handlers.remove(task))
                            connection.read_handlers.add(reader)
                            
                except asyncio.CancelledError:
                    return # We return as the connection closing is handled by self.close()
                except Exception as e:
                    self.logger.error(f'IPC connection error ({e})')
                    
        except asyncio.CancelledError:
            return # We return as the connection closing is handled by self.close()
        except ConnectionError as e:
            self.logger.error(f'IPC connection failed ({e})')
            return
        except Exception as e:
            self.logger.error(f'IPC connection error ({e})')
        
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
        
    async def sendMessage(self, message: Union[str, int, float], connection: Union[Connection, Iterable[Connection]]=None, blocking: bool=False) -> bool:
        '''
        Send a message to either one or more connections.
        This function by default is a fire & forget method, but when set
        to `blocking=True` waits if the message could be dispatched to all
        recipients.
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
            
            # Dispatch message to affected connections as long as we're not shutting down
            if len(connections) > 0 and not self._shutdown:                
                writer = asyncio.gather(
                    *[self._dispatchMessage(message, c) for c in connections],
                    loop=self.loop,
                    return_exceptions=True
                    )
                
                # Adding as many callbacks as connections, so the future (writer) gets removed from all connections
                for c in connections:
                    def cancel_writer(connection, writer):
                        print('------> CALLBACK')
                        try:
                            connection.write_handlers.remove(writer)
                        except Exception as e:
                            print('CALLBACK ERROR', e)
                    writer.add_done_callback(functools.partial(cancel_writer, c))
                    c.write_handlers.add(writer)
                    
                if not blocking:
                    print('<- RETURING IMMEDIATELY')
                    return True
                else:
                    #PROBLEM HIER IST; DASS ANSCHEINED DAS DIESE FUNCTION EXTERN AUFGRUFEN WIRD UND NICHT
                    #GECANCELLED WIRD; ODER? BEI NON-BLOCKING IST ES KEIN PROBLEM
                    print('...WAITING FOR WRITER')
                    for c in connections:
                        print(len(c.write_handlers))
                    await writer
                    return all(not isinstance(success, Exception) for success in writer)
                    
                    # ODER for response in await writer:
                
            else:
                return False
        except asyncio.CancelledError:
            return False
        except Exception as e:
            print(e)
            return False
        
    async def _dispatchMessage(self, message: bytes, connection: Connection) -> bool:
        try:
            if not connection.writer.transport.is_closing():
                # Dispatch message
                connection.writer.write(message)
                await connection.writer.drain()
                
                print('DISPATCHING')
                await asyncio.sleep(5)
                
                # Close an ephemeral connection, immediately after sending the message
                if connection.state['mode'] == ConnectionType.EPHEMERAL:
                    await self.closeConnection(connection)
                # Return result
                return True
            else:
                raise freedmIPCMessageWriter(e)   
        except asyncio.CancelledError:
            print('Im a writer and got CANCELLED')
            return
        except Exception as e:
            print('KACKE PASSIERT BEIM DISPATCHEN!', type(e), e)
            return freedmIPCMessageWriter(e)
    
    async def close(self) -> None:
        '''
        Stop this server
        '''
        await self.__aexit__()