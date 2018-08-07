'''
This module extends the RPyC module by own server implementations.
For further information read: 
@author: Thomas Wanderer
'''

# Imports
import asyncio
import logging
import sys

# RPyC imports
try:
    from rpyc.core import SocketStream, Channel, Connection
    from rpyc.utils.registry import UDPRegistryClient
    from rpyc.utils.authenticators import AuthenticationError
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)

@asyncio.coroutine
def registerPeriodically(function, interval):
    while True:
        yield from asyncio.sleep(interval)
        function()

class AsyncIOServer:
    '''
    This RPyC server utilizes the AsyncIO loop instead of Threads.
    It is based on: https://github.com/tomerfiliba/rpyc/issues/175 and
    the principles of this article https://pymotw.com/3/asyncio/io_coroutine.html
    '''
    
    def __init__(self, service, hostname='', ipv6=False, port=0,
            backlog=10, reuse_addr=True, authenticator=None, registrar=None,
            auto_register=None, protocol_config={}, logger=None, listener_timeout=0.5):

        self.service = service
        self.authenticator = authenticator
        self.backlog = backlog
        self.protocol_config = protocol_config
        
        if auto_register is None:
            self.auto_register = bool(registrar)
        else:
            self.auto_register = auto_register
            
        if ipv6 and hostname == "localhost" and sys.platform != "win32":
            # On windows, you should bind to localhost even for ipv6
            hostname = "localhost6"
            
        self.hostname = hostname
        self.port = port

        if logger is None:
            logger = logging.getLogger("%s/%d" % (self.service.get_service_name(), self.port))
        self.logger = logger
        if "logger" not in self.protocol_config:
            self.protocol_config["logger"] = self.logger
        if registrar is None:
            registrar = UDPRegistryClient(logger=self.logger)
        self.registrar = registrar

        # The AsyncIO Server object
        self.server = None

        # Unused parameters
        self.reuse_addr = reuse_addr
        self.listener_timeout = listener_timeout
        
    def close(self):
        '''
        Closes (terminates) the server and all of its clients. If applicable,
        also unregisters from the registry server.
        '''
        # Unregister from RPyC registry
        if self.auto_register:
            try:
                self.registrar.unregister(self.port)
            except Exception:
                self.logger.exception("error unregistering services")
        
        # Close the AsyncIO server and loop
        self.logger.info('closing server')
        self.server.close()
        self.loop.run_until_complete(self.server.wait_closed())
        self.logger.info('closing event loop')
        self.loop.close()

    def fileno(self):
        '''
        Returns the listener socket's file descriptor
        '''
        return self.server.sockets[0]

    def _accept_method(self, reader, writer):
        self._authenticate_and_serve_client(reader, writer)

    def _authenticate_and_serve_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        if self.authenticator:
            addrinfo = writer.transport.get_extra_info("peername")
            h = addrinfo[0]
            p = addrinfo[1]
            try:
                credentials = self.authenticator(reader, writer)
            except AuthenticationError:
                self.logger.info("[%s]:%s failed to authenticate, rejecting connection", h, p)
                return
            else:
                self.logger.info("[%s]:%s authenticated successfully", h, p)
        else:
            credentials = None

        try:
            self._serve_client(reader, writer, credentials)
        except Exception:
            self.logger.exception("client connection terminated abruptly")
            raise
        writer.close()

    def _serve_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, credentials):
        addrinfo = writer.transport.get_extra_info("peername")
        h = addrinfo[0]
        p = addrinfo[1]
        sockname = writer.transport.get_extra_info("sockname")
        sock = writer.transport.get_extra_info("socket")
        if credentials:
            self.logger.info("welcome [%s]:%s (%r)", h, p, credentials)
        else:
            self.logger.info("welcome [%s]:%s", h, p)
        try:
            config = dict(self.protocol_config,
                          credentials=credentials,
                          endpoints=(sockname, addrinfo),
                          logger=self.logger
                          )
            conn = Connection(self.service,
                              Channel(SocketStream(sock)),
                              config=config,
                              _lazy=True
                              )
            conn._init_service()
            conn.serve_all()
        finally:
            self.logger.info("goodbye [%s]:%s", h, p)

    def _bg_register(self):
        aliases = self.service.get_service_aliases()
        try:
            self.registrar.register(aliases, self.port, interface=self.hostname)
        except:
            self.logger.exception("error registering services")

    def start(self):
        '''
        Starts the AsyncIO server and periodically register with the RPyC registry
        '''
        
        # Start the AsyncIO server with the loop
        self.loop = asyncio.get_event_loop()
        server = asyncio.start_server(self._accept_method, self.hostname, self.port, loop=self.loop, backlog=self.backlog)
        self.server = self.loop.run_until_complete(server)
        self.logger.info("server started on [%s]:%s", self.hostname, self.port)
        
        # Register
        if self.auto_register:
            self._bg_register()
            asyncio.create_task(registerPeriodically(self._bg_register, self.registrar.REREGISTER_INTERVAL))

        # Run loop forever
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            print("")
            self.logger.warn("keyboard interrupt!")
        finally:
            self.logger.info("server has terminated")
            self.close()