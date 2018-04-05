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
    from typing import Union, Type, Optional, Any
    
    # free.dm Imports
    from freedm.utils.ipc.server.base import IPCSocketServer
    from freedm.utils.ipc.exceptions import freedmIPCSocketCreation, freedmIPCSocketShutdown
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
    Alternatively it is possible to provide a pre-created socket. In this case, the address-family is ignored.
    '''
    
    def __init__(
            self,
            address: str=None,
            port: int=None,
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
        self.address = address if address else ''
        self.port = port
        self.family = family
        self.socket = socket
        
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
        # The socket object to bind to
        sock = [self.socket] if self.socket else None
        
        # The address family set or preferred
        family = socket.AF_UNSPEC if self.family == AddressType.AUTO or self.family == AddressType.DUAL \
            else socket.AF_INET6 if self.family != AddressType.IPV4 and socket.has_ipv6 else socket.AF_INET
        
        if not sock:
            try:
                # Get the correct address information for the corresponding family
                addresses = socket.getaddrinfo(self.address, self.port, family=family, type=socket.SOCK_STREAM, proto=0, flags=socket.AI_PASSIVE+socket.AI_CANONNAME)
                
                # Collect addresses we need to bind to based on the specified+supported address families
                connect_to = []
                
                # In case we explicitly want an IPv6 socket
                if family in (socket.AF_INET, socket.AF_INET6) and len(addresses) > 0:
                    connect_to.append(addresses[0])
                
                # In case we want to auto-detect, we prefer IPv6 over IPv4 if supported and IPv6-address available
                elif self.family == AddressType.AUTO:
                    addresses.sort(key=lambda x: x[0] == socket.AF_INET6, reverse=socket.has_ipv6)
                    connect_to.append(addresses[0])
                
                # In case we want to use dual stack
                elif self.family == AddressType.DUAL:
                    for a in addresses:
                        if a[0] == socket.AF_INET:
                            connect_to.append(a)
                            break
                    for a in addresses:
                        if a[0] == socket.AF_INET6:
                            connect_to.append(a)
                            break
                    
                
                print('-------------------------------------------------------')
                for address in connect_to:
                    for i,v in enumerate('family, type, proto, canonname, sockaddr'.split(', ')):
                        print(v, '=', address[i])
                    print('-------------------------------------------------------')

                
                return
            
                '''
                Hier weitermachen! Wenn nur ein socket, dann alles ganz normal. Aber falls DUALstack, müssen wir noch testen
                '''
                
                # Try to create a socket from the address infos
                for c in connect_to:
                    try:
                        family, type, protocol, canonical_name, socket_address = c
                        sock = socket.socket(
                            family,
                            type,
                            protocol
                            )
                        sock.bind(socket_address)
                        #sock.listen(queue_size)
                    except socket.error as e:
                        if sock is not None: sock.close()
                            
            except socket.gaierror as e:
                raise freedmIPCSocketCreation(f'Cannot create TCP server socket for address "{self.address}:{self.port}" (Address not supported by family "{socket.AddressFamily(family).name}")')
            except Exception as e:
                raise freedmIPCSocketCreation(f'Cannot create TCP server socket for address "{self.address}:{self.port}" ({e})')
        
        # Create TCP socket server
        try:
            if sock:
                server_options=dict(
#                     flags=None,
                    reuse_address=True,
                    loop=self.loop,
                    ssl=None,
                    backlog=100,
                    sock=sock
                    )
                if self.limit:
                    server_options.update({'limit': self.limit})
                    print(server_options)
                    server = await asyncio.start_server(
                        self._onConnectionEstablished,
                        host=None, #self.address,
                        port=None, #self.port,
                        **server_options
                        )
            else:
                raise Exception('Could not assemble socket object')
        except Exception as e:
            raise freedmIPCSocketCreation(f"Cannot create TCP server {'with socket' if self.socket else 'at address'} \"{sock if self.socket else f'{self.address}:{self.port}'}\" ({e})")
        
        # Return server
        return server
    
    async def _post_shutdown(self) -> None:
        self.logger.debug(f'IPC server closed (TCP socket "{self.address}:{self.port}")')
                           
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