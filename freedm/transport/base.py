'''
This module defines the base object for all transport objects
@author: Thomas Wanderer
'''

# free.dm Imports

try:
    # Imports
    import textwrap
    from typing import TypeVar, Optional, Type
    
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
    The base class for all transports (Server, Clients, Nodes, ...)
    '''
    
    # An identifier name for this client (Used for logging purposes). By default set to the class-name
    name: str=None
    
    def __init__(
            self,
            protocol: Optional[Protocol] = None
            ) -> None:
        
        self.logger = logging.getLogger()
        if not self.name:
            self.name = self.__class__.__name__
        if protocol:
            self.setProtocol(protocol)
    
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
        Stop this server
        '''
        await self.__aexit__()
        
    def setProtocol(self, protocol: Protocol) -> None:
        '''
        Sets a new messaging protocol for this transport
        '''
        self.protocol = protocol
        
    async def handleMessage(self, message: Message) -> None:
        '''
        This method either handles the message itself when overwritten by a subclass
        or passes the message to the protocol's handler.
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
            self.logger.debug(f'{self.name} detected a failing client connection')
      
    async def handleClientDisconnect(self, connection: Connection) -> None:
        '''
        This method is called when this client disconnects from the transport server.
        Should be overwritten by a subclass or implemented by protocol.
        '''
        try:
            await self.protocol.handleClientDisconnect(connection)
        except:
            self.logger.debug(f'A {self.name} client disconnected')
          
    async def handleLimitExceedance(self, connection: Connection, sender: Type[T])  -> None:
        '''
        This method is called when an incoming or outgoing message is too large exceeding the set limit.
        Should be overwritten by a subclass or implemented by protocol.
        '''
        try:
            await self.protocol.handleLimitExceedance(connection)
        except:
            self.logger.debug(f'A {sender.__class__.__name__}\'s message exceeded the set limit "{self.limit}"')