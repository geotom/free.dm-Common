'''
This module defines a client communicating via UXD sockets
@author: Thomas Wanderer
'''

try:
    # Imports
    import os
    import asyncio
    import socket
    import time
    from pathlib import Path
    from typing import Optional, Type, Union
    
    # free.dm Imports
    from freedm.transport.client.base import TransportClient
    from freedm.transport.exceptions import freedmSocketCreation, freedmSocketShutdown
    from freedm.transport.protocol import Protocol
    from freedm.transport.connection import Connection, ConnectionType
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


class UXDSocketClient(TransportClient):
    '''
    A client connecting to transport servers via an Unix Domain Socket.
    '''
    
    # The UXD socket
    _socket: socket.socket=None
    
    def __init__(
            self,
            path: Union[str, Path]=None,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            timeout: int=None,
            limit: Optional[int]=None,
            lines: Optional[bool]=False,
            chunksize: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol]=None
            ) -> None:
        
        super().__init__(loop, timeout, limit, lines, chunksize, mode, protocol)
        self.path = path
        
    async def _init_connect(self):
        if not self.path:
            raise freedmSocketCreation('Cannot create UXD socket (No socket file provided)')
        try:
            # Create UXD socket (Based on https://www.pythonsheets.com/notes/python-socket.html)
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            self._socket.connect(self.path)
            reader, writer = await asyncio.open_unix_connection(sock=self._socket, loop=self.loop)
            return self._assembleConnection(reader, writer)
        except Exception as e:
            raise freedmSocketCreation(f'Cannot connect to UXD socket file "{self.path}" ({e})')
        
    async def _post_disconnect(self, connection) -> None:
        if self._socket:
            sock = self._socket
            self._socket = None
            try:
                sock.close()
            except Exception as e:
                raise freedmSocketShutdown(e)
            self.logger.debug(f'Transport closed (UXD socket "{self.path}")')
            return
                           
    def _assembleConnection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Connection:
        return Connection(
            socket=writer.get_extra_info('socket'),
            pid=os.getpid(),
            uid=os.getuid(),
            gid=os.getgid(),
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