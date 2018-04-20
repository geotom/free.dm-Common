'''
This module defines a server communicating via UXD sockets
@author: Thomas Wanderer
'''

try:
    # Imports
    import os
    import stat
    import asyncio
    import socket
    import struct
    import time
    from pathlib import Path
    from typing import Union, Type, Optional, Any
    
    # free.dm Imports
    from freedm.transport.server.base import TransportServer
    from freedm.transport.exceptions import freedmSocketCreation, freedmSocketShutdown
    from freedm.transport.connection import Connection, ConnectionType
    from freedm.transport.protocol import Protocol
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


class UXDSocketServer(TransportServer):
    '''
    A server using Unix Domain sockets implemented as async contextmanager.
    This server can restrict clients access by their group and user memberships.
    '''
    
    def __init__(
            self,
            path: Union[str, Path]=None,
            group_only: bool=False,
            user_only: bool=False,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            limit: Optional[int]=None,
            chunksize: Optional[int]=None,
            lines: Optional[bool]=False,
            max_connections: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol]=None
            ) -> None:
        
        super().__init__(loop, limit, lines, chunksize, max_connections, mode, protocol)
        self.path = path
        self.group_only = group_only
        self.user_only = user_only

    async def _init_server(self) -> Any:
        if not self.path:
            raise freedmSocketCreation('Cannot create UXD socket (No socket file provided)')
        elif os.path.exists(self.path):
            # Remove any previous file/directory
            if os.path.isdir(self.path):
                raise freedmSocketCreation(f'Cannot create UXD socket because "{self.path}" is a directory ({e})')
            else:
                try:
                    os.remove(self.path)
                except Exception as e:
                    raise freedmSocketCreation(f'Cannot delete UXD socket file "{self.path}" ({e})')
        try:
            # Create UXD socket (Based on https://www.pythonsheets.com/notes/python-socket.html)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(self.path)
            
            # Secure socket
            if self.user_only:
                os.chmod(self.path, stat.S_IREAD | stat.S_IWRITE)
            elif self.group_only and not self.user_only:
                os.chmod(self.path, stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP)
        except Exception as e:
            raise freedmSocketCreation(f'Cannot create UXD socket file "{self.path}" ({e})')
        
        # Create UDP socket server
        if self.limit:
            server = await asyncio.start_unix_server(self._onConnectionEstablished, loop=self.loop, sock=sock, limit=self.limit)
        else:
            server = await asyncio.start_unix_server(self._onConnectionEstablished, loop=self.loop, sock=sock)
        
        # Return server
        return server

    async def _post_shutdown(self) -> None:
        # Clean up by removing the UXD socket file
        try:
            os.remove(self.path)
        except Exception as e:
            raise freedmSocketShutdown(e)
        self.logger.debug(f'{self.name} closed (UXD socket "{self.path}")')
        
    def _assembleConnection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Connection:
        sock = writer.get_extra_info('socket')
        credentials = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
        pid, uid, gid = struct.unpack('3i', credentials)
        return Connection(
            socket=sock,
            pid=pid,
            uid=uid,
            gid=gid,
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