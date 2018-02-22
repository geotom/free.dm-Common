'''
The generic service class exposing API methods for all daemons
@author: Thomas Wanderer
'''

# Imports
import time, uuid
from datetime import timedelta
from typing import Dict

# RPyC imports
try:
    from rpyc import Service
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)

# free.dm Imports
from freedm.utils.types import TypeChecker as checker


class ClientService(Service):
    '''
    The PyRC service class used by clients to expose a fixed set of RPC methods to connected servers
    '''
    def exposed_printMessage(self, message):
        '''
        Prints a message sent to the stout of the client
        :param str message: The message
        :raises ValueError: If the message exceeds 160 characters
        :raises TypeError: If the message is not a basestring
        '''
        max_length=160
        if checker.isString(message):
            if(len(message) <= max_length):
                print(message)
            else:
                raise ValueError(f'Message exceeds {max_length} characters')
        else:
            raise TypeError('Not a string')
        
    def exposed_getUserContext(self):
        '''
        Returns the current user and group context of the client script
        :return: A tuple with UID, GID
        :rtype: tuple
        '''
        import os, getpass, grp
        return (getpass.getuser(), grp.getgrgid(os.getgid())[0])
    
    def exposed_haltClient(self):
        '''
        Stops and disconnects the client
        '''
        import sys
        sys.exit()

    
class DaemonService(Service):
    '''
    The PyRC service class used by daemons to expose a fixed set of RPC methods for connected clients
    '''
    # A service ID to identify service instances created for each client session
    id = None
    
    @property
    def daemon(self):
        '''The daemon instance running this service'''
        try:
            return getattr(self, '__daemon')
        except:
            raise AttributeError('Daemon instance is not set')
    @daemon.setter
    def daemon(self, instance):
        if self.__daemon == None:
            self.__daemon = instance
        else:
            raise AttributeError('Daemon instance is already set')
        
    # Init
    def __init__(self, conn):
        # Call the parent __init__ method on creation
        super().__init__(conn)
        
        # Give this service instance an ID hash
        self.id = uuid.uuid4().hex
        
        # Bind the daemon's serverValue Getters & Setters to local functions
        self.setServerValue = self.daemon.setServerValue
        self.getServerValue = self.daemon.getServerValue
        
        # Use the daemon's logger
        self.logger = self.daemon.logger
        
    def on_connect(self):
        # Tag the connection with a connection timestamp
        self._conn.TIME = time.time()
        # Add the connection to the daemons connections cache
        self.daemon._addRpcConnection(self._conn)
        # Call the abstract method on the daemon instance
        self.daemon.onRpcConnect()
    
    def on_disconnect(self):
        # Call the abstract method on the daemon instance
        self.daemon.onRpcDisconnect()
        
    # Daemon related exposed methods
    def exposed_queryDaemon(self):
        '''
        Will query the daemon's API and return the results
        '''
        pass
    
    def exposed_reloadDaemon(self, data=None):
        '''
        Reloads the daemon configuration and will trigger a restart
        :param data: The data storage path or py:class:::freedm.data.objects.DataStorage
        '''
        pass
    
    def exposed_stopDaemon(self, timeout=10):
        '''
        Stops the daemon and disconnects all clients
        :param int timeout: Client keeps the connection alive for the specified timeout in seconds (default 10)
        '''
        # Set the state to "stopping" and the daemon's stopper thread will recognize this and will halt the daemon
        self.daemon.state = 'stopping'
        # Wait for timeout
        for s in range(0, abs(timeout)):
            if self.daemon.state == 'stopping':
                time.sleep(1)
            elif self.daemon.state == 'idle' or self.daemon.state == 'crashed':
                break
    
    def exposed_getDaemonUptime(self) -> str:
        ''' 
        Returns the uptime of this daemon instance as formated string
        :return: The daemon uptime
        :rtype: str
        '''
        return str(timedelta(seconds=float(time.time() - self.getServerValue('uptime'))))
    
    def exposed_getSystemUptime(self):
        ''' 
        Returns the uptime of this OS system as formated string
        :return: The OS uptime
        :rtype: str
        '''
        try:
            with open('/proc/uptime', 'r') as file:
                return str(timedelta(seconds=float(file.readline().split()[0])))
        except:
            return ''
        
    def exposed_getDaemonInfo(self):
        '''
        Return the most important information regarding the daemon instance,
        thus as the class, role, state, etc.
        :return: The daemon instance data
        :rtype: dict
        '''
        if self.daemon:
            return dict(
                type    = checker.getExactType(self.daemon),
                role    = self.daemon.role.capitalize(),
                state   = self.daemon.state.capitalize(),
                pid     = self.daemon.pid,
                version = self.daemon.version,
                address = self.daemon.host if not '127.0.0.1' else 'localhost',
                port    = self.daemon.port
                )
        else:
            return {}
    
    def exposed_getSystemInfo(self) -> Dict:
        ''' 
        Returns a dictionary with gathered daemon data & system info
        :return: The daemon data & system info
        :rtype: dict
        '''
        import platform
        import freedm.utils.system
        from datetime import timedelta
        
        # Build a dictionary with daemon info 
        info = self.exposed_getDaemonInfo()
        info.update(freedm.utils.system.getSystemInfo(self.daemon.pid))       
        info.update(dict(
            network         = f'{platform.node()}@{self.daemon.data.getConfig("freedm.network.name", "freedm.network.name")}',
            system_uptime   = self.exposed_getSystemUptime(),
            daemon_uptime   = self.exposed_getDaemonUptime(),
            sessions        = []
            ))
        
        # Get a list of RPC sessions
        for c in self.daemon._getRpcConnections():
            if c != self._conn:
                try:
                    info['sessions'].append(dict(
                        address=c._channel.stream.sock.getpeername()[0],
                        port=c._channel.stream.sock.getpeername()[1],
                        duration=str(timedelta(seconds = float(time.time() - c.TIME)))
                        ))
                except:
                    pass
                
        # Get the user & security context
        info.update({'user': freedm.utils.system.getUserInfo()})
        
        from freedm.utils.formatters import printPrettyDict
        printPrettyDict(info)
        
        return info
    
    def exposed_keepalive(self):
        '''
        Keeps the client connection alive by looping until the session gets terminated or the server closes
        '''
        # Add this connection to the session pool
        session = self.daemon._startRpcSession(self)
        # Loop while the daemon is running 
        if session:
            # Remember last state
            state = self.daemon.state
            # Loop as long this connection persists
            while True:
                current_state = self.daemon.state
                if current_state in ('running', 'stopping') and session._closed is not True and self.daemon._closed is not True:
                    # Update state
                    state = current_state
                    try:
                        # Check if connection is still alive and sleep
                        session.poll()
                        time.sleep(2)
                    except EOFError:
                        break
                else:
                    # If state has changed
                    if state != current_state:
                        if current_state == 'loading':
                            self.daemon.notifyRpcClient(session, 'Server is reloading')
                        if current_state == 'crashed':
                            self.daemon.notifyRpcClient(session, 'Server failure occurred')
                        if current_state == 'idle':
                            pass
                    break