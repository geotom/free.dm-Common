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
    from freedm.utils.ipc.exceptions import freedmIPCSocketCreation
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
    
    def __init__(
            self,
            path: Union[str, Path]=None,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            limit: Optional[int]=None,
            chunksize: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol]=None
            ) -> None:
        
        super(self.__class__, self).__init__(loop, limit, chunksize, mode, protocol)
        self.path = path
        
    async def __aenter__(self) -> UC:
        # Create UXD socket (Based on https://www.pythonsheets.com/notes/python-socket.html)
        if not self.path:
            raise freedmIPCSocketCreation(f'Cannot create UXD socket (No socket file provided)')
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            sock.connect(self.path)
            reader, writer = await asyncio.open_unix_connection(sock=sock, loop=self.loop)
            self._connection = self._assembleConnection(reader, writer)
            self._handler = asyncio.ensure_future(self.handleMessage(self._connection.reader))
        except Exception as e:
            raise freedmIPCSocketCreation(f'Cannot connect to UXD socket file "{self.path}" ({e})')
        finally:
            return self
        
    async def __aexit__(self, *args) -> None:
        pass
        
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
                'creation': time.time(),
                'update': time.time()
                }
            )