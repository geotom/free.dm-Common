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
    import ssl
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
    
    Security:
    To secure the communication between the client and server, pass a pre-setup SSL
    context object as parameter. Be aware that you need to set an address for the server
    if you verify the host certificate via " SSLContext.check_hostname".
    '''
    
    # The UXD socket
    _socket: socket.socket=None
    
    def __init__(
            self,
            path: Union[str, Path]=None,
            address: str=None,
            sslctx: ssl.SSLContext=None,
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
        self.address = address
        self.sslctx = sslctx
        
    async def _init_connect(self):
        if not self.path:
            raise freedmSocketCreation('Cannot create UXD socket (No socket file provided)')
        try:
            # Create & connect to UXD socket (Based on https://www.pythonsheets.com/notes/python-socket.html)
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
            self._socket.connect(self.path)
            # Update SSL context
            if self.sslctx and self.sslctx.check_hostname:
                if not self.address or self.address == '':
                    raise Exception(f'SSL: No peer address provided while checking for hostname')
                def handshake_callback(ssl_socket, server_name, ssl_context) -> None:
                    self.logger.debug(f'{self.name} trying to verify peer by name "{server_name}" ({"Optional" if not self.sslctx.verify_mode == ssl.CERT_REQUIRED else "Required"})')
                    return None
                self.sslctx.set_servername_callback(handshake_callback)
            # Start client connection
            client_options=dict(
                loop=self.loop,
                ssl=self.sslctx,
                sock=self._socket,
                server_hostname=(self.address or '') if self.sslctx else None
                )
            if self.limit:
                client_options.update({'limit': self.limit})
            reader, writer = await asyncio.open_unix_connection(**client_options)
            return self._assembleConnection(reader, writer)
        except ssl.CertificateError as e:
            raise freedmSocketCreation(f'Cannot connect to UXD socket at "{self.path}" (SSL Error: {e})')
        except Exception as e:
            raise freedmSocketCreation(f'Cannot connect to UXD socket at "{self.path}" ({e})')
        
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
            sslctx=writer.get_extra_info('sslcontext') if self.sslctx else None,
            sslobj=writer.get_extra_info('ssl_object') if self.sslctx else None,
            pid=os.getpid(),
            uid=os.getuid(),
            gid=os.getgid(),
            peer_cert=writer.get_extra_info('peercert') if self.sslctx else None,
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