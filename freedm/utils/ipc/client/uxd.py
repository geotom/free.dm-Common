'''
This module defines an IPC client communicating via UXD sockets
@author: Thomas Wanderer
'''

try:
    # Imports
    import os
    import asyncio
    import socket
    import time
    from pathlib import Path
    from typing import TypeVar, Optional, Type, Union
    
    # free.dm Imports
    from freedm.utils.ipc.client.base import IPCSocketClient
    from freedm.utils.ipc.exceptions import freedmIPCSocketCreation, freedmIPCSocketShutdown
    from freedm.utils.ipc.protocol import Protocol
    from freedm.utils.ipc.message import Message
    from freedm.utils.ipc.connection import Connection, ConnectionType
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


UC = TypeVar('UC', bound='UXDSocketClient')


class UXDSocketClient(IPCSocketClient):
    '''
    An IPC client connecting to IPC servers via an Unix Domain Socket.
    '''
    
    # The UXD socket
    _socket: socket.socket=None
    
    def __init__(
            self,
            path: Union[str, Path]=None,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            timeout: int=None,
            limit: Optional[int]=None,
            chunksize: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol]=None
            ) -> None:
        
        super().__init__(loop, timeout, limit, chunksize, mode, protocol)
        self.path = path
        
    async def __aenter__(self) -> UC:
        # Call parent (Required to profit from SaveContextManager)
        await super().__aenter__()
        
        if not self.path:
            raise freedmIPCSocketCreation('Cannot create UXD socket (No socket file provided)')
        try:
            # Create UXD socket (Based on https://www.pythonsheets.com/notes/python-socket.html)
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            self._socket.connect(self.path)
            reader, writer = await asyncio.open_unix_connection(sock=self._socket, loop=self.loop)
            await self._onConnectionEstablished(self._assembleConnection(reader, writer))
        except Exception as e:
            self._connection = None
            self._handler = None
            raise freedmIPCSocketCreation(f'Cannot connect to UXD socket file "{self.path}" ({e})')
        
        # Return self
        return self
        
    async def _post_disconnect(self, connection) -> None:
        if self._socket:
            sock = self._socket
            self._socket = None
            try:
                sock.close()
            except Exception as e:
                raise freedmIPCSocketShutdown(e)
            self.logger.debug(f'IPC connection closed (UXD socket "{self.path}")')
                                
    def _assembleConnection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Connection:
        '''
        Assemble a connection object based on the info we get from the reader/writer
        '''
        return Connection(
            socket=writer.get_extra_info('socket'),
            pid=os.getpid(),
            uid=os.getuid(),
            gid=os.getgid(),
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