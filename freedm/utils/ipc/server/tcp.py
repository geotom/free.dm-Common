'''
This module defines an IPC server communicating via TCP
@author: Thomas Wanderer
'''

try:
    # Imports
    import os
    import asyncio
    import socket
    import contextlib
    import time
    import ssl
    from typing import Union, Type, Optional, Any
    
    # free.dm Imports
    from freedm.utils.ipc.server.base import IPCSocketServer
    from freedm.utils.ipc.exceptions import freedmIPCSocketCreation
    from freedm.utils.ipc.connection import Connection, ConnectionType, AddressType
    from freedm.utils.ipc.protocol import Protocol
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


class TCPSocketServer(IPCSocketServer):
    '''
    An IPC server binding using TCP implemented as async contextmanager.
    This server supports both IPv4 and IPv6 in the following modes:
    - IPV4: IPv4 only
    - IPV6: IPv6 only
    - DUAL: Binding to an IPv4 and IPv6 address
    - AUTO: Automatically using the address-families available with a preference for IPv6
    Alternatively it is possible to provide a pre-created socket or list of sockets. In this case, 
    the address-family is ignored. The server can bind to more than one address. Provide a 
    comma-separated list of interface addresses to bind to.  
    '''
    
    def __init__(
            self,
            address: Union[str, list]=None,
            port: int=None,
            sslctx: ssl.SSLContext=None,
            family: Optional[AddressType]=AddressType.AUTO,
            socket: socket.socket=None,
            loop: Optional[Type[asyncio.AbstractEventLoop]]=None,
            limit: Optional[int]=None,
            chunksize: Optional[int]=None,
            max_connections: Optional[int]=None,
            mode: Optional[ConnectionType]=None,
            protocol: Optional[Protocol]=None
            ) -> None:
        
        super().__init__(loop, limit, chunksize, max_connections, mode, protocol)
        self.address = address if isinstance(address, list) else [address]
        self.port = port
        self.family = family
        self.socket = socket
        self.sslctx = sslctx
        
    def supports_dualstack(self, sock: socket.socket=None) -> bool:
        '''
        Checks if the system kernel supports dual stack sockets, listening to both: IPv4 + IPv6
        If a socket is provided, the check is made against the provided socket
        '''
        try:
            socket.AF_INET6
            socket.IPPROTO_IPV6
            socket.IPV6_V6ONLY
        except AttributeError:
            return False
        try:
            if sock is not None:
                return not sock.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY)
            else:
                sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                with contextlib.closing(sock):
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                    return True
        except socket.error:
            return False
        
    async def _init_server(self) -> Any:
        # The server or servers to return
        servers = []
        
        # The address family type set or preferred
        address_type = socket.AF_UNSPEC if self.family == AddressType.AUTO or self.family == AddressType.DUAL \
            else socket.AF_INET6 if self.family != AddressType.IPV4 and socket.has_ipv6 else socket.AF_INET
        
        # The socket object to bind to
        sockets = self.socket if isinstance(self.socket, list) else ([self.socket] if self.socket else [])
        
        # Create sockets if none were provided
        if len(sockets) == 0:
            for a in self.address:
                # Get the correct address information for the corresponding family
                try:
                    addresses = socket.getaddrinfo(a, self.port, family=address_type, type=socket.SOCK_STREAM, proto=0, flags=socket.AI_PASSIVE+socket.AI_CANONNAME)
                except socket.gaierror as e:
                    self.logger.error(f'Cannot resolve IPC server address "{a}:{self.port}" (Address not supported by family "{socket.AddressFamily(address_type).name}")')
                    continue
                
                # Create a new sockets
                try:
                    # Collect addresses we need to bind to based on the specified+supported address families
                    connect_to = []
                    address_duo = []
                    
                    # In case we explicitly want an IPv4 or IPv6 socket
                    if address_type in (socket.AF_INET, socket.AF_INET6) and len(addresses) > 0:
                        connect_to.append(addresses[0])
                    
                    # In case we want to auto-detect, we prefer IPv6 over IPv4 if supported and IPv6-address available
                    elif self.family == AddressType.AUTO:
                        addresses.sort(key=lambda x: x[0] == socket.AF_INET6, reverse=socket.has_ipv6)
                        connect_to.append(addresses[0])
                    
                    # In case we want to use dual stack
                    elif self.family == AddressType.DUAL:
                        for a in addresses:
                            if a[0] == socket.AF_INET6:
                                address_duo.append(a)
                                break
                        # Only add an IPv4 address if dualstack is not supported or no IPv6 address is available
                        if len(address_duo) == 0 or not self.supports_dualstack():
                            for a in addresses:
                                if a[0] == socket.AF_INET:
                                    address_duo.append(a)
                                    break
                        # Add address duo to other addresses
                        connect_to += address_duo
                        
                    # Try to create a socket from the address info
                    for c in connect_to:
                        try:
                            a_family, a_type, a_protocol, a_canonical_name, a_address = c
                            sock = socket.socket(
                                a_family,
                                a_type,
                                a_protocol
                                )
                            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            if self.family == AddressType.DUAL and len(address_duo) <= 1:
                                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                            sock.bind(a_address)
                            sockets.append(sock)
                            self.logger.debug(f'IPC server bound to TCP socket with {"IPv4" if a_family == socket.AF_INET else "IPv6"}-address "{a_canonical_name or a_address}:{self.port}"')
                        except socket.error as e:
                            self.logger.error(f'IPC server cannot bind to TCP socket with {"IPv4" if a_family == socket.AF_INET else "IPv6"}-address "{a_canonical_name or a_address}:{self.port}"')
                            if sock is not None: sock.close()
                except Exception as e:
                    self.logger.error(f'IPC server cannot create TCP sockets for address "{a}:{self.port}" ({e})')
                    continue
                
        # Create TCP socket server
        try:
            if len(sockets) > 0:
                for sock in sockets: 
                    server_options=dict(
                        reuse_address=True,
                        loop=self.loop,
                        ssl=self.sslctx,
                        backlog=100,
                        sock=sock
                        )
                    if self.limit:
                        server_options.update({'limit': self.limit})
                        server = await asyncio.start_server(
                            self._onConnectionEstablished,
                            **server_options
                            )
                        servers.append(server)
            else:
                raise Exception('Could not setup TCP sockets')
        except Exception as e:
            raise freedmIPCSocketCreation(f"Cannot create TCP server {'with socket(s)' if self.socket else 'at address(es)'} \"{','.join(sock) if self.socket else ','.join(map(lambda x: f'{x}:{self.port}', self.address)) }\" ({e})")
        
        # Return server
        return servers
    
    async def _pre_shutdown(self) -> None:
        self.SHUTDOWN = [(s.sockets[0].family, s.sockets[0].getsockname()) for s in self._server]
    
    async def _post_shutdown(self) -> None:
        if self.SHUTDOWN:
            for sock in self.SHUTDOWN:
                self.logger.debug(f'IPC server closed TCP socket with {"IPv4" if sock[0] == socket.AF_INET else "IPv6"}-address "{sock[1][0]}:{self.port}"')
            del self.SHUTDOWN
                           
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
        
    # Gute Zusammenfassung
    #https://erlerobotics.gitbooks.io/erle-robotics-python-gitbook-free/network_data_and_network_errors/network_exceptions.html
 
    # Dualstack
    # !!! http://code.activestate.com/recipes/578504-server-supporting-ipv4-and-ipv6/
    # !!! https://stackoverflow.com/questions/16762939/use-of-in6addr-setv4mapped-and-dual-stack-sockets
    
    # https://www.pythonsheets.com/notes/python-socket.html
    # http://asyncio.readthedocs.io/en/latest/tcp_echo.html
    
#     addr = writer.get_extra_info('peername')
#     print("Received %r from %r" % (message, addr))

    # Mit IP6 oder nicht?
    # https://www.pythonsheets.com/notes/python-socket.html#simple-tcp-echo-server-through-ipv6
    # https://www.pythonsheets.com/notes/python-socket.html#disable-ipv6-only
    # 