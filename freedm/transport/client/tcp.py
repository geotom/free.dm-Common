'''
This module defines a transport client communicating via TCP sockets
@author: Thomas Wanderer
'''

try:
    # Imports
    import os
    import asyncio
    import ssl
    import socket
    import time
    from typing import Optional, Type, Union 
    
    # free.dm Imports
    from freedm.transport.client.base import TransportClient
    from freedm.transport.exceptions import freedmSocketCreation, freedmSocketShutdown
    from freedm.transport.protocol import Protocol
    from freedm.transport.connection import Connection, ConnectionType, AddressType
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


class TCPSocketClient(TransportClient):
    '''
    A client connecting to transport servers via TCP socket.
    This client supports both IPv4 and IPv6 addresses in the following modes:
    - IPV4: IPv4 only
    - IPV6: IPv6 only
    - AUTO: Automatically using the address-families available with a preference for IPv6
    
    To secure the communication between the client and server, pass a pre-setup SSL
    context object as parameter.
    '''
        
    # The TCP socket
    _socket: socket.socket=None
    
    def __init__(
            self,
            
            address: Union[str, list]=None,
            port: int=None,
            sslctx: ssl.SSLContext=None,
            family: Optional[AddressType]=AddressType.AUTO,
            socket: socket.socket=None,
            
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            timeout: int=None,
            limit: Optional[int]=None,
            lines: Optional[bool]=False,
            chunksize: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol]=None
            ) -> None:
        
        super().__init__(loop, timeout, limit, lines, chunksize, mode, protocol)
        self.address = address
        self.port = port
        self.family = family
        self._socket = socket
        self.sslctx = sslctx
        
    async def _init_connect(self):
        address_type = socket.AF_UNSPEC if self.family == AddressType.AUTO else (socket.AF_INET6 if self.family != AddressType.IPV4 and socket.has_ipv6 else socket.AF_INET)
        connect_to = None
        
        # Get the correct address information for the corresponding family
        try:
            addresses = socket.getaddrinfo(self.address, self.port, family=address_type, type=socket.SOCK_STREAM, proto=0, flags=socket.AI_PASSIVE+socket.AI_CANONNAME)
        except socket.gaierror as e:
            raise freedmSocketCreation(f'Cannot resolve {self.name} address "{self.address}:{self.port}" (Address not supported by family "{socket.AddressFamily(address_type).name}")')
        
        # In case we explicitly want an IPv4 or IPv6 socket
        if address_type in (socket.AF_INET, socket.AF_INET6) and len(addresses) > 0:
            connect_to = addresses[0]
        
        # In case we want to auto-detect, we prefer IPv6 over IPv4 if supported and IPv6-address is available
        elif self.family == AddressType.AUTO:
            addresses.sort(key=lambda x: x[0] == socket.AF_INET6, reverse=socket.has_ipv6)
            connect_to = addresses[0]
        
        # Create socket if none was provided
        if not self._socket:
            # Try to create a socket from the address info
            try:
                a_family, a_type, a_protocol, a_canonical_name, a_address = connect_to
                self._socket = socket.socket(
                    a_family,
                    a_type,
                    a_protocol
                    )
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except socket.error as e:
                if self._socket is not None: self._socket.close()
                raise freedmSocketCreation(f'Cannot create TCP socket for {"IPv4" if a_family == socket.AF_INET else "IPv6"}-address "{a_canonical_name or a_address}:{self.port}" ({e})')
        
        # Connect the socket
        try:
            self._socket.connect(a_address)
            client_options=dict(
                loop=self.loop,
                ssl=self.sslctx,
                sock=self._socket,
                server_hostname=self.address if self.sslctx else None
                )
            if self.limit:
                client_options.update({'limit': self.limit})
            reader, writer = await asyncio.open_connection(**client_options)
            return self._assembleConnection(reader, writer)
        except ssl.CertificateError as e:
            raise freedmSocketCreation(f'Cannot connect to TCP server with {"IPv4" if a_family == socket.AF_INET else "IPv6"}-address "{a_canonical_name or a_address}:{self.port}" (SSL Error: {e})')
        except Exception as e:
            raise freedmSocketCreation(f'Cannot connect to TCP server with {"IPv4" if a_family == socket.AF_INET else "IPv6"}-address "{a_canonical_name or a_address}:{self.port}" ({e})')
        
    async def _post_disconnect(self, connection) -> None:
        if self._socket:
            sock = self._socket
            self._socket = None
            try:
                sock.close()
            except Exception as e:
                raise freedmSocketShutdown(e)
            self.logger.debug(f'Transport closed (TCP socket with {"IPv4" if sock.family == socket.AF_INET else "IPv6"}-address "{self.address}:{self.port}")')
            return
                           
    def _assembleConnection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Connection:
        sock = writer.get_extra_info('socket')
        return Connection(
            socket=sock,
            pid=os.getpid(),
            uid=os.getuid(),
            gid=os.getgid(),
            peer_address=sock.getpeername(),
            host_address=sock.getsockname(),
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