'''
This module defines the base object for all transport objects
and defines a common interface. any of the methods are just
template methods awaiting their implementation in a subclass.
@author: Thomas Wanderer
'''

# free.dm Imports

try:
    # Imports
    import textwrap
    import time
    import asyncio
    from typing import TypeVar, Optional, Union, Iterable
    
    # free.dm Imports
    from freedm.utils import logging
    from freedm.utils.async import BlockingContextManager
    from freedm.transport.protocol import Protocol
    from freedm.transport.message import Message
    from freedm.transport.connection import Connection, ConnectionType
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


T = TypeVar('T', bound='Transport')


# Base Transport class
class Transport(BlockingContextManager):
    '''
    The base class for all transports (Server, Clients, Nodes, ...).
    This is an awaitable class. Alternatively it also can be called as 
    context manager. All other transpot nodes need to subclass from this base class.
    '''
    
    # An identifier name for this transport entity (Used for logging purposes). By default set to the class-name
    name: str=None
    
    # The default line separator used for reading lines
    line_separator: str='\n'
    
    def __init__(
            self,
            protocol: Optional[Protocol] = None
            ) -> None:
        
        self.logger = logging.getLogger()
        if not self.name:
            self.name = self.__class__.__name__
        if protocol:
            self.setProtocol(protocol)
            
    async def __await__(self) -> T:
        '''
        Template method: Makes this class awaitable
        '''
        return await self.__aenter__()
    
    async def __aenter__(self) -> T:
        '''
        Template method: Make this class work like an async context manager
        '''
        # Call parent (Required to profit from BlockingContextManager)
        await super().__aenter__()
        return self
    
    async def __aexit__(self, *args) -> None:
        '''
        Template method: Make this class work like an async context manager
        '''
        await super().__aexit__(*args)
    
    async def _dispatchMessage(self, message: bytes, connection: Connection) -> bool:
        '''
        The actual coroutine dispatching the message to the connection's socket writer.
        It might close the connection depending on its mode.
        '''
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
                return False
        except:
            return False
    
    async def close(self) -> None:
        '''
        Stop this transport endpoint
        '''
        await self.__aexit__()
        
    def connected(self) -> bool:
        '''
        Template method: This template method checks if the transport is connected and its sockets alive.
        Please implement a transport specific check.
        '''
        return True
        
    def setProtocol(self, protocol: Protocol) -> None:
        '''
        Sets a new messaging protocol for this transport. A protocol implements a communication logic between two
        or more transport endpoints. Many of the transport handlers try to pass the handling of events to the set
        protocol handlers.
        '''
        self.protocol = protocol
        
    def _assembleConnection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Connection:
        '''
        Template method: Assemble a connection object based on the info we get from the reader/writer.
        Might be overridden by a subclass method to set different parameters
        '''
        return Connection(
            socket=writer.get_extra_info('socket'),
            sslctx=None,
            sslobj=None,
            pid=None,
            uid=None,
            gid=None,
            cert=None,
            peer_address=None,
            host_address=None,
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
        
    async def _handleConnection(self, connection: Connection) -> None:
        '''
        Template method: Observe transport connection and listen for incoming messages until we receive an EOF.
        '''
        try:
            while not connection.reader.at_eof():
                raw = await connection.reader.read(self.limit or -1)
                if raw and not len(raw) == 0:
                    message = Message(
                        data=raw,
                        sender=connection
                        )
                    await self.handleMessage(message)
            self.close()
        except asyncio.CancelledError:
            return
        except ConnectionError as e:
            self.logger.error(f'Transport failed ({e})')
            return
        except Exception as e:
            self.logger.error(f'Transport error ({e})')           
            
    async def authenticateConnection(self, connection: Connection) -> bool:
        '''
        Template method: This method either authenticates a new peer itself when overwritten by a subclass
        or passes the message to the protocol's handler.
        '''
        try:
            return await self.protocol.authenticate(connection)
        except:
            return True
        
    async def closeConnection(self, connection: Connection, reason: Optional[str]=None) -> None:
        '''
        End and close an existing connection:
        Acknowledge or inform the peer about EOF, then close.
        '''
        if connection and not connection.writer.transport.is_closing():
            # Tell transport the reason
            if reason:
                await self.sendMessage(reason, connection)
            try:
                connection.state['closed'] = time.time()
                if connection.reader.at_eof():
                    self.logger.debug('Transport closed by peer')
                    connection.reader.feed_eof()
                    await self.handlePeerDisconnect(connection)
                else:
                    self.logger.debug(f'Transport closed by {self.name}')
                    if connection.writer.can_write_eof(): connection.writer.write_eof()
                await asyncio.sleep(.1)
                connection.writer.close()
            except:
                pass
            finally:
                # Make sure we set this in any case
                if not connection.state['closed']:
                    connection.state['closed'] = time.time()
                self.logger.debug('Transport writer closed')
        
    async def rejectConnection(self, connection: Connection, reason: Optional[str]=None) -> None:
        '''
        A method rejecting (closing) a new connection attempt. An optional reason can be provided and gets sent to the peer
        before closing (reject) the new connection again.
        '''
        self.logger.debug(f'Rejecting new connection ({reason})')
        await self.closeConnection(connection, reason=reason)
        
    async def handleMessage(self, message: Message) -> None:
        '''
        This method handles inbound messages. The handling is passed to the transport's protocol when set.
        '''
        try:
            await self.protocol.handleMessage(message)
        except:
            self.logger.debug(f'{self.name} received: {textwrap.shorten(message.data.decode(), 50, placeholder="...")}')
    
    async def handleConnectionFailure(self, connection: Connection) -> None:
        '''
        This method is called when a connection failed, for instance when the socket is dead.
        Should be overwritten by a subclass or implemented by protocol.
        '''
        try:
            await self.protocol.handleConnectionFailure(connection)
        except:
            self.logger.debug(f'{self.name} detected a failed connection')
      
    async def handlePeerDisconnect(self, connection: Connection) -> None:
        '''
        This method is called when a peer disconnects from this transport host.
        Should be overwritten by a subclass or implemented by protocol.
        '''
        try:
            await self.protocol.handlePeerDisconnect(connection)
        except:
            self.logger.debug(f'A {self.name} peer disconnected')
          
    async def handleLimitExceedance(
        self,
        connection: Union[Connection, Iterable[Connection]],
        message: Union[str, int, float, bytes],
        inbound: bool
        ) -> None:
        '''
        This method is called when an in- or outbound message is too large and exceeding a set limit.
        Should be overwritten by a subclass or implemented by protocol.
        '''
        message = message.decode() if isinstance(message, bytes) else str(message)
        try:
            await self.protocol.handleLimitExceedance(connection, message, inbound)
        except:
            self.logger.error(f'{"Inbound" if inbound else "Outbound"} message "{textwrap.shorten(message, 25, placeholder="...")}" size exceeds set limit of {self.limit} bytes.')