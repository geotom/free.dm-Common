'''
This module defines the base transport server. 
Subclass from this class to create a custom transport server implementation.
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    import time
    import textwrap
    import functools
    from typing import Union, Type, Optional, TypeVar, Iterable, Any, List
    
    # free.dm Imports
    from freedm.utils import logging
    from freedm.utils.async import getLoop
    from freedm.utils.types import TypeChecker as checker
    from freedm.transport.base import Transport
    from freedm.transport.message import Message
    from freedm.transport.protocol import Protocol
    from freedm.transport.connection import Connection, ConnectionType, ConnectionPool
    from freedm.transport.exceptions import freedmMessageLimitOverrun
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


TS = TypeVar('TS', bound='TransportServer')


class TransportServer(Transport):
    '''
    A generic transport server implementation for allowing to communicate with connected clients
    while keeping a list of active connections. It can be used as a contextmanager or as asyncio awaitable.
    This server provides basic functionality for receiving and sending messages and supports:
    - Ephemeral and persistent (long-living) connections
    - Setting a maximum connection limit
    - Limiting amount of data sent or received
    - Reading data at once or in chunks
    - Client authentication
    
    Connection types:
    By default a server keeps connections alive (persistent) until an EOF is detected. But alternatively 
    it can be set to close the connection immediately after sending a message to the connected client (ephemeral).
    
    Connection establishment:
    Any newly created client connection will be checked against an optional maximum parallel connection limit 
    and the client might be rejected if the limit has been surpassed. If a client connections gets accepted, 
    the specific server implementation should further authenticate the client and reject it as well on failure.
    
    Reading & sending data:
    First of all, all message IO is handled in a non-blocking asynchronous manner. The server knows several
    strategies when reading and sending messages. The reading by default is ...
    '''
    
    # The context (This server)
    _server: Union[Type[asyncio.AbstractServer], List[Type[asyncio.AbstractServer]]]=None
    
    # A register for active client connections
    _connection_pool: ConnectionPool=None
    
    # A state flag
    _shutdown: bool=False
    
    def __init__(
            self,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            limit: Optional[int]=None,
            lines: Optional[bool]=False,
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
        self.lines      = lines
        
        if not self.name:
            self.name = self.__class__.__name__
        if not self._connection_pool:
            self._connection_pool = ConnectionPool()
        if checker.isInteger(max_connections):
            self._connection_pool.max = max_connections
        if protocol:
            self.setProtocol(protocol)
        
    async def __aenter__(self) -> TS:
        '''
        A template function that should be implemented by any subclass
        '''
        # Call parent (Required to profit from BlockingContextManager)
        await super().__aenter__()
        
        # Initialize and create a server a server
        self._server = await self._init_server()

        # Check & Return self
        if not self._server: self.logger.error(f'{self.name} could not be started')
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
                    if not reader.done(): reader.cancel()
                for writer in connection.write_handlers:
                    if not writer.done(): writer.cancel()
            asyncio.wait(
                [await cancel_connection_handlers(c) for c in connections],
                timeout=None,
                loop=self.loop
                )
        except Exception as e:
            self.logger.error(f'Problem shutting down {self.name} gracefully ({e})')
        
        # Close the server oder servers if more than one
        try:
            self._server.close()
        except AttributeError:
            for server in self._server:
                server.close()
        except Exception as e:
            self.logger.error(f'Cannot shutdown {self.name} ({e})')
        try:   
            await self._server.wait_closed()
        except AttributeError:
            for server in self._server:
                await server.wait_closed()
        except Exception as e:
            self.logger.error(f'Could not wait until {self.name} shutdown ({e})')    
        
        # Call post-shutdown procedure
        await self._post_shutdown()
            
        # Call parent (Required to profit from SaveContextManager)
        await super().__aexit__()
    
    def _onConnectionEstablished(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> asyncio.Task:
        '''
        Responsible for the creation and recycling of connections for any new established session
        and subsequently hands over the further session handling
        '''
        # Build a connection object
        connection = self._assembleConnection(reader, writer)
        
        # Check if max connection is not exceeded?
        if self._connection_pool.isFull():
            session = asyncio.ensure_future(self.rejectConnection(connection, 'Too many connections'), loop=self.loop)
        else:
            session = asyncio.ensure_future(self._handleConnection(connection), loop=self.loop)
            self._connection_pool.add(session)
            session.add_done_callback(lambda task: self._connection_pool.remove(session))
        return session
    
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
                self.logger.debug('Client connection was successfully authenticated')
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
                                self.logger.error(f'Client connection limit is smaller than chunksize. Closing connection.')
                                break
                            if rest <= 0:
                                self.logger.debug(f'Client connection limit "{self.limit}" reached. Closing connection.')
                                break
                            chunksize = chunksize if rest > chunksize else rest
                        raw = await connection.reader.read(chunksize)
                        chunks += 1
                    # Read line by line (Respecting set limit)
                    elif self.lines:
                        try:
                            raw = await connection.reader.readuntil(separator=b'\n')
                        except asyncio.IncompleteReadError as e:
                            self.logger.error(f'Client message exceeds limit "{self.limit}".')
                            raw = ''
                        except asyncio.CancelledError as e:
                            raise e
                        except Exception as e:
                            raw = ''
                    # Default read (Respecting set limit)
                    else:
                        raw = await connection.reader.read(self.limit or -1)
                        
                    # Handle the received message or message fragment
                    if not len(raw) == 0:
                        message = Message(
                            data=raw,
                            sender=connection
                            )
                        # Never launch another message handler while we're being shutdown (this task getting cancelled)
                        if not self._shutdown and not connection.state['closed']:
                            reader = asyncio.ensure_future(self.handleMessage(message), loop=self.loop)
                            reader.add_done_callback(lambda task: connection.read_handlers.remove(task) if connection.read_handlers and task in connection.read_handlers else None)
                            connection.read_handlers.add(reader)
                except asyncio.CancelledError:
                    return # We return as the connection closing is handled by self.close()
                except Exception as e:
                    self.logger.error(f'Transport error ({e})')
        except asyncio.CancelledError:
            return # We return as the connection closing is handled by self.close()
        except ConnectionError as e:
            self.logger.error(f'Transport failed ({e})')
            return
        except Exception as e:
            self.logger.error(f'Transport error ({e})')
        
        # Close the connection (It will be automatically removed from the pool)
        await self.closeConnection(connection)
            
    async def sendMessage(self, message: Union[str, int, float], connection: Union[Connection, Iterable[Connection]]=None, blocking: bool=False) -> bool:
        '''
        Send a message to either one or more connections.
        This function by default is a fire & forget method, but when set
        to `blocking=True` waits if the message could be dispatched to all
        recipients. Only the latter returns a real (boolean) result, 
        telling if the message could be successfully written to (not received by) 
        the client(s)
        '''
        try:
            # Get affected connections
            affected = [connection] if not checker.isIterable(connection) else connection
            connections = [c for c in affected if not c.state['closed']]
    
            # Encode and check message
            message = str(message)
            if self.lines and not message.endswith('\n'):
                message += '\n'
            message = message.encode()
            if len(message) == 0:
                return False
            if self.limit and len(message) > self.limit:
                self.logger.error(f'Outgoing message exceeds limit "{self.limit}" ({textwrap.shorten(message, 50, placeholder="...")}).')
                raise freedmMessageLimitOverrun()
            
            # Dispatch message to affected connections as long as we're not shutting down
            if len(connections) > 0 and not self._shutdown:
                writer = asyncio.gather(
                    *[self._dispatchMessage(message, c) for c in connections],
                    loop=self.loop,
                    return_exceptions=True
                    )
                
                # Adding as many callbacks as connections, so the future (writer) gets removed from all connections
                def cancel_writer(connection, writer):
                    try:
                        connection.write_handlers.remove(writer)
                    except:
                        pass
                for c in connections:
                    writer.add_done_callback(functools.partial(cancel_writer, c))
                    c.write_handlers.add(writer)
                
                # Return behavior
                if not blocking:
                    return True
                else:
                    await writer
                    return all(r for r in writer.result())
            else:
                return False
        except:
            return False