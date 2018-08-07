'''
This module defines the base transport client. Subclass from
this class to create a custom transport client implementation.
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    import time
    from typing import TypeVar, Optional, Type, Union
    
    # free.dm Imports
    from freedm.utils import logging
    from freedm.utils.aio import getLoop
    from freedm.transport.base import Transport
    from freedm.transport.message import Message
    from freedm.transport.protocol import Protocol
    from freedm.transport.connection import Connection, ConnectionType
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


TC = TypeVar('TC', bound='TransportClient')


class TransportClient(Transport):
    '''
    A generic client implementation to connect to transport servers. It can be used 
    as a contextmanager or as asyncio awaitable. It supports basic message 
    exchange and can be configured with a protocol for advanced communication.
    A client can:
    - Establish ephemeral and persistent (long-living) connections
    - Limiting amount of data sent or received
    - Read data at once or in chunks
    
    Reading & sending data:
    First of all, all message IO is handled in a non-blocking asynchronous manner. The client knows several
    strategies when reading and sending messages. The reading by default is simply to read from the socket up to an 
    optional set limit or everything that arrives.
    This can be changed to:
    - Simply read all or up to an optional limit
    - Read line by line (but only up to an optional line size limit)
    - Read in chunks up to an optional total data limit
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
            lines: Optional[bool]=False,
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
        self.lines      = lines
        
        if not self.name:
            self.name = self.__class__.__name__
        if protocol:
            self.setProtocol(protocol)
        
    async def __aenter__(self) -> TC:
        '''
        A template function that should be implemented by any subclass
        '''
        # Call parent (Required to profit from BlockingContextManager)
        await super().__aenter__()
        
        # Call pre-connection preparation
        connection = await self._init_connect()
        
        # Connect
        if connection: self._onConnectionEstablished(connection)

        # Call post-connection preparation
        if connection: await self._post_connect(connection)

        # Check & Return self
        if not connection: self.logger('Transport could not be established')
        return self
        
    async def __aexit__(self, *args) -> None:
        '''
        Cancel the connection handler and close the connection
        '''
        
        if not self.connected(): return
        
        # Set internals to None again
        handler = self._handler
        connection = self._connection
        self._handler = None
        self._connection = None
             
        # Call pre-shutdown procedure
        await self._pre_disconnect(connection)
        
        # Cancel the handler  
        if handler: handler.cancel()
            
        # Inform server of disconnection and cancel read/write handlers
        if connection:
            await self.closeConnection(connection)
            for reader in connection.read_handlers:
                reader.cancel()
            for writer in connection.write_handlers:
                writer.cancel()
            
        # Call post shutdown procedure
        await self._post_disconnect(connection)

        # Call parent (Required to profit from SaveContextManager)
        await super().__aexit__(*args)

    def connected(self) -> bool:
        '''
        Checks if the connection is still alive
        '''
        return (self._connection and not self._connection.state['closed'])
    
    def _onConnectionEstablished(self, connection: Connection) -> None:
        '''
        This function stores the connection and initializes a handler for it
        '''
        # Set connection and start the handler task
        self._connection = connection
        
        # Start the connection handler
        try:
            self.logger.debug(f'{self.name} successfully established connection')
            if not self.timeout:
                self._handler = asyncio.ensure_future(
                    self._handleConnection(self._connection),
                    loop=self.loop
                    )
            else:
                self._handler = asyncio.ensure_future(
                    asyncio.wait_for(
                        self._handleConnection(self._connection),
                        self.timeout,
                        loop=self.loop
                        )
                )
        except Exception as e:
            self.logger.debug('Transport connection handler could not be initialized')
    
    async def _init_connect(self) -> Optional[Connection]:
        '''
        Template function for initializing a connection.
        It should return a connection object.
        '''
        return
    
    async def _post_connect(self, connection: Connection) -> None:
        '''
        Template function called after the establishment of a connection
        '''
        return
    
    async def _pre_disconnect(self, connection: Connection) -> None:
        '''
        Template function to prepare the closing of the connection
        before we cancel the connection handler
        '''
        return
    
    async def _post_disconnect(self, connection: Connection) -> None:
        '''
        Template function to cleanup after the connection closing was
        signaled via self.closeConnection
        '''
        return
    
    async def _handleConnection(self, connection: Connection) -> None:
        '''
        Handle the connection and listen for incoming messages until we receive an EOF.
        '''
        try:
            # Read data depending on the connection type and handle it
            raw = None
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
                                self.logger.error(f'Set message size limit of {self.limit} bytes is smaller than chunksize {chunksize}. Closing connection.')
                                break
                            if rest <= 0:
                                self.logger.debug(f'Total message size limit of {self.limit} bytes reached. Closing connection.')
                                break
                            chunksize = chunksize if rest > chunksize else rest
                        raw = await connection.reader.read(chunksize)
                        chunks += 1
                    # Read line by line (Respecting set limit)
                    elif self.lines:
                        try:
                            raw = await connection.reader.readuntil(separator=self.line_separator.encode())
                        except asyncio.LimitOverrunError as e:
                            raw = await connection.reader.read(e.consumed + len(self.line_separator.encode()))
                            await self.handleLimitExceedance(connection, raw, True)
                            continue
                        except asyncio.IncompleteReadError as e:
                            if len(e.partial) > 0:
                                raw = e.partial
                            else:
                                continue
                        except asyncio.CancelledError as e:
                            raise e
                        except Exception as e:
                            self.logger.error(f'Incoming message cannot be read ({e})')
                            continue
                    # Default read (Respecting set limit)
                    else:
                        raw = await connection.reader.read(self.limit or -1)
                    
                    # Handle the received message or message fragment by a new non-blocking task
                    if raw and not len(raw) == 0:
                        message = Message(
                            data=raw,
                            sender=connection
                            )
                        # Never launch another message handler while we're being disconnected (this task getting already cancelled)
                        if (self._handler and not self._handler.done()) and not connection.state['closed']:
                            reader = asyncio.ensure_future(self.handleMessage(message), loop=self.loop)
                            reader.add_done_callback(lambda task: connection.read_handlers.remove(task) if connection.read_handlers and task in connection.read_handlers else None)
                            connection.read_handlers.add(reader)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.error(f'Transport error ({e})')
        except asyncio.CancelledError:
            pass
        except ConnectionError as e:
            await self.handleConnectionFailure(connection)
        except Exception as e:
            self.logger.error(f'Transport error ({e})')
        
        # Close this connection again
        await self.close()
    
    async def sendMessage(self, message: Union[str, int, float], blocking: bool=False) -> bool:
        '''
        Send a message to either one or more connections
        This function by default is a fire & forget method, but when set
        to `blocking=True` waits if the message could be dispatched to the
        recipient. Only the latter returns a real (boolean) result, 
        telling if the message could be successfully written to (not received by) 
        the client(s)
        '''
        try:
            # Encode and check message
            message = str(message)
            if self.lines and not message.endswith(self.line_separator):
                message += self.line_separator
            message = message.encode()
            if len(message) == 0:
                return False
            if self.limit and len(message) > self.limit:
                await self.handleLimitExceedance(self._connection, message, False)
                return False
            
            # Dispatch message as long as not we're being disconnected (this task getting cancelled)
            if self._connection and not self._handler.done() and not self._connection.state['closed']:
                # Dispatch and store future with a callback
                writer = asyncio.ensure_future(self._dispatchMessage(message, self._connection), loop=self.loop)
                writer.add_done_callback(lambda task: self._connection.write_handlers.remove(task) if self._connection and task in self._connection.write_handlers else None)
                self._connection.write_handlers.add(writer)
                
                # Return behavior
                if not blocking:
                    return True
                else:
                    await writer
                    return writer.result()
            else:
                return False
        except:
            return False