'''
The generic daemon class for all free.dm daemons
@author: Thomas Wanderer
'''

# Imports
import os
import time
import argparse
try:
    import psutil
except ImportError as e:
    print(f'Missing dependency ({e}): Please install via "pip install psutil"')
from threading import Thread
from typing import Dict, List

# RPyC imports
try:
    from rpyc.utils.server import ThreadPoolServer, ThreadedServer
    from rpyc.utils.authenticators import AuthenticationError
except ImportError as e:
    print(f'Missing dependency ({e}): Please install via "pip install rpyc"')

# free.dm Imports
from freedm.utils import logger as L
from freedm.utils import globals as G
from freedm.data.objects import DataManager, IniFileStore
from freedm.utils.types import TypeChecker as checker
from freedm.utils.exceptions import ExceptionHandler
from freedm.daemons.client import DaemonClient
from freedm.daemons.service import DaemonService

class GenericDaemon(ThreadedServer):
    '''
    The generic daemon class for all other free.dm entity servers. Each entity in the free.dm
    framework performs a different role, tasks and services. Each server role should extent this base daemon class.
    It defines the common attributes and methods each server daemon needs to have.
    '''
        
    __states = (
        'idle',
        'starting',
        'running',
        'loading',
        'stopping',
        'crashed'
        )
    
    # Intermediate dictionary for service class generation. Gets reset after the GenericService has been created
    __rpc = {}
    
    # A daemon specific data sore (dictionary) working as persistent key/value-storage across all RPyC connections (exposed methods)
    __store = {}
    
    # The sub thread started by this daemon instance
    __subthreads = {
        'watchdog': None,
        'services': None
        }
    
    # Sessions for kept alive connections
    __sessions : Dict = {}
    
    # The Threaded RPyC server does not keep a queue of active connections so we do this instead
    __connections = []
    
    __logger = None
    @property
    def logger(self):
        '''The logger of this class'''
        if self.__logger is None:
            return L.getLogger(level=G.VERBOSITY)
        else:
            return self.__logger
    @logger.setter
    def logger(self, logger):
        if checker.isExactType(logger, 'logging.Logger') or checker.isExactType(logger, 'logging.RootLogger'):
            self.__logger = logger
            
    __data = None
    @property
    def data(self):
        '''The data path used by this class'''
        return self.__data
    @data.setter
    def data(self, location):
        # The default data management location
        if isinstance(location, DataManager):
            # Set the data location
            self.__data = location
        else:
            # Create a default data manager
            self.__data = DataManager(location)
    
    _role = 'generic'
    @property
    def role(self):
        '''Every daemon fulfills a certain role. This is the role's name'''
        return self._role
    @role.setter
    def role(self, role):
        raise AttributeError('You are not allowed to change the role of a daemon instance')
    
    _state = 'idle'
    @property
    def state(self):
        '''The current execution state of the daemon'''
        return self._state
    @state.setter
    def state(self, state):
        if state in self.__states:
            self._state = state
            
    _version = G.VERSION
    @property
    def version(self):
        '''The version of this daemon'''
        return self._version
    @version.setter
    def version(self, version):
        raise AttributeError('You cannot change the version of a daemon instance')
            
    _pid = os.getpid()
    @property
    def pid(self):
        '''The process id of the daemon process'''
        return self._pid
    @pid.setter
    def pid(self, pid):
        raise AttributeError('You cannot change the process id of an instance')
            
    @classmethod
    def isRunning(self):
        '''
        Checks if an instance of this class is already running by looking up the list of system processes
        :returns: ``True`` if an running instance can be found
        :rtype: bool
        '''
        # Additional imports
        import subprocess, sys, re
        
        # Get this script's environment
        cwd     = os.getcwd()
        exe     = sys.argv[0]
        abs     = os.path.abspath(os.path.join(cwd, exe))
        file    = os.path.basename(exe)
           
        # Get a list of possible processes (matching the script name and invocation method)
        nulldevice  = open(os.devnull, 'w')
        command     = f'ps ax -o pid= -o args= | grep "{file} [A-Za-z].* start"'
        try:
            for line in subprocess.check_output(command, shell=True , stderr=nulldevice).decode('utf-8').strip().split('\n'):
                try:                        
                    # Get the PID related process info and compare to the scripts environment
                    p = psutil.Process(int(re.split('\s+', line)[0]))
                    try:
                        p_abs = os.path.abspath(os.path.join(p.cwd(), p.cmdline()[1]))
                    except psutil.AccessDenied:
                        if p.cmdline()[1].endswith(file):
                            p_abs = p.cmdline()[1]
                        else:
                            p_abs = ''
                    # Check if the found process shares the same absolute path with this script
                    # But make sure the process runs under a different PID
                    if p.pid != self._pid and abs == p_abs:
                        return True
                except:
                    pass
        except:
            return False
        # No process found so far? Return false!
        return False
        
    @classmethod
    def rpcmethod(self, function):
        '''
        This class methods is a decorator function adding the provided function as exposed 
        RPyC method to this daemon instance. RPyC methods are then callable for instance via command-line 
        connections and represent an internally exposed set of private methods a RPyC client can 
        use or which can be used by other daemon sub-modules.
        The ``self`` attribute in RPC methods represents the py:class::freedm.daemons.service.DaemonService.
        To access the current daemon instance of this service class use ``self.daemon``
        :param function function: The function to expose as daemon RPyC service method 
        '''
        self.__rpc.update({f'exposed_{function.__name__}': function})
               
    # Representation
    def __repr__(self) -> str:
        return '<{}@{}:{} (Process: {})>'.format(
            self.__class__.__name__,
            self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
            self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port'),
            self.pid
            )

    # Class instance creation
    def __new__(cls, parser=None, logger=None):
        '''
        Returns the daemon class to instantiate. Either a GenericDaemon (sub)class or a DaemonClient if 
        a running daemon is detected. We interrupt the creation of the daemon to see if we need to create 
        a GenericDeamon instance and spawn it or just return a DaemonClient to interact with the running 
        daemon instance. Based on the default or the provided parser inputs, we will decide how to proceed.
        '''
        # Get the parent class and the daemon role definition from the class
        parent  = super()
        role    = cls.__dict__['_role']
        
        # The default parser handlers
        def daemonHandler(arguments):
            # The action to execute
            action = arguments.action
    
            # Execute server method
            if cls.isRunning():
                # Create a client connection to the running daemon
                client = DaemonClient(data=G.DATA, logger=logger)
                # Execute the action
                if client.connected:
                    if action == 'start':
                        print(f'{role.capitalize()} daemon is already running')
                    elif action == 'info':
                        client.getDaemonInfo()
                    elif action == 'reload':
                        client.reloadDaemon()
                    elif action == 'stop':
                        client.stopDaemon()
                else:
                    print(f'Cannot connect to {role} daemon')
                # Return the client
                return client
            else:
                if action == 'start':
                    # Create and return a GenericDaemon or subclass instance
                    return parent.__new__(cls)
                else:
                    print(f'{role.capitalize()} daemon not running')
        
        def queryHandler(arguments):
            # In case of zero arguments
            if len(arguments._get_args()) is 0:
                parser.print_help()
            else:
                print(arguments._get_args())
        
        def monitorHandler(arguments):
            # Open a persistent connection to the server instance
            client = DaemonClient(data=G.DATA, logger=logger, persistent=True)
            if not client._exception is None:
                print(f'{role.capitalize()} daemon not running')
            return client
        
        # Get the provided parser or setup the default argument parser object
        try:
            if not isinstance(parser, argparse.ArgumentParser):
                raise Exception
        except:
            parser = argparse.ArgumentParser(
                prog=os.path.basename(__file__),
                description=f'The free.dm {role.capitalize()} console:',
                add_help=True
                )
            
        subparser = parser.add_subparsers(
            help='Module description',
            dest='module'
            )
        subparser_defaults = argparse.ArgumentParser(add_help=False)
        subparser_defaults.add_argument(
            '--verbosity',
            type=int,
            metavar='INT',
            help=f'Regulate the output verbosity (Default={G.VERBOSITY})',
            default=G.VERBOSITY
            )
        subparser_defaults.add_argument(
            '--config',
            type=str,
            metavar='FOLDER',
            help='Provide an alternative config location',
            default=G.DATA
            )
        subparser_defaults.add_argument(
            '--debug',
            action='store_true',
            help='Set the debug mode',
            default=False
            )
        
        # Daemon control subparser
        parser_daemon = subparser.add_parser(
            'server',
            help=f'Control the {role} daemon',
            description=f'Start and control the free.dm {role} daemon:',
            parents=[subparser_defaults]
            )
        parser_daemon.set_defaults(handler=daemonHandler)
        parser_daemon.add_argument(
            'action',
            choices=['start', 'stop', 'reload', 'info']
            )
         
        # Query menu subparser
        parser_query = subparser.add_parser(
            'query',
            help=f'Query the {role} API',
            description=f'Query the free.dm {role} API:',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            parents=[subparser_defaults]
            )
        parser_query.set_defaults(handler=queryHandler)
        parser_query.add_argument(
            'module',
            choices=['module 1', 'module 2', 'module 3', 'module 4']
            )
        
        # Monitor console subparser
        parser_monitor = subparser.add_parser(
            'monitor',
            help=f'Monitor the {role} daemon',
            description='Start a monitoring console displaying daemon events',
            parents=[subparser_defaults]
            )
        parser_monitor.set_defaults(handler=monitorHandler)
         
        # Get parsed arguments from executed script
        arguments = parser.parse_args()
        
        # Invoke the corresponding argument handler ...
        if hasattr(arguments, 'handler'):
            # Set verbosity level
            if hasattr(arguments, 'verbosity') and arguments.verbosity in range(1, 6):
                G.VERBOSITY = (6 - arguments.verbosity) * 10
                
            # Set debug mode based on environment/arguments
            if (hasattr(arguments, 'debug') and arguments.debug):
                G.MODE = 'debug'
                
            # Create a default logger if not set (only after we updated the G.MODE and G.VERBOSITY)
            from logging import Logger
            logger = logger if isinstance(logger, Logger) else L.getLogger(level=G.VERBOSITY)
                
            # Create the DataManager (Only after we setup the logger)
            if hasattr(arguments, 'config'):
                G.DATA = DataManager(arguments.config)
                
            # Set Error handler (Only after we set the G.MODE))
            G.ERROR = ExceptionHandler(G.MODE)
            
            # Invoke handler and return its result instance (if either daemon or client)
            result = arguments.handler(arguments)
            if isinstance(result, cls):
                return result
            elif isinstance(result, DaemonClient):
                return result
            else:
                return None
            
        # ... or show the help message as default output instead
        else:
            parser.print_help()
            
    # Init 
    def __init__(self, parser=None, logger=None):
        '''
        ATTENTION: Be aware that creating any py:class::freedom.daemon.GenericDaemon might return either
        an instance of a GenericDaemon or a py:class::freedom.client.DaemonClient depending on a daemon already 
        running or not! So please do not rely on the created daemon being a daemon instance in every case.
        Do a check first!
        
        Inits the daemon. You can provide your own py:class::argparse.ArgumentParser to this daemon.
        By default a freedm daemon supports a standard ArgumentParser and will add certain subparsers
        to the provided ArgumentParser for starting/stopping the daemon and for accessing daemon worker modules
        or creating a live console.
        :param parser: An optional py:class::argparse.ArgumentParser (default: None)
        :param logger: An optional py:class::logging.Logger (default: None)
        '''
        # Set logger & data manager
        self.logger = logger
        self.data = G.DATA
        
        # Add the daemon's configuration store to data manager
        self.data.registerStore(
            IniFileStore(
                **{
                    'name': 'Configuration',
                    'alias': 'config',
                    'filetype': 'config',
                    'synced': True
                    }
                )
            )
        
        # Spawn the daemon and init the superclass
        self._spawnDaemon()
        
    def setServerValue(self, key, value):
        '''
        A setter method for the server's global persistent data store. The values set in this store are available to all client sessions
        :param str key: A key name
        :param value: Any value
        '''
        self.__store.update({key: value})
    
    def getServerValue(self, key):
        '''
        A getter method for the server's global persistent data store. The values set in this store are available to all client sessions
        :param str key: A key name
        :returns: The corresponding key value or ’’None’’ if not set
        '''
        if key in self.__store:
            return self.__store[key]
        else:
            return None
        
    def _addRpcConnection(self, connection):
        '''
        Adds the current connection to a cache to make a ThreadedServer daemon aware of all current connections
        :param connection: py:class::rpyc.core.protocol.Connection connection
        '''
        if isinstance(self, ThreadedServer):
            # Clean old connections before adding the new one
            self._getRpcConnections()
            # Now add the new connection
            self.__connections.append(connection)
            
    def _getRpcConnections(self):
        '''
        Returns the list of active client connection objects, connected to this daemon
        :returns: The list of current py:class::rpyc.core.protocol.Connection connections 
        :rtype: list
        '''
        connections = []
        if isinstance(self, ThreadPoolServer):
            for k in self.fd_to_conn.keys():
                connections.append(self.fd_to_conn[k])
            return connections
        elif isinstance(self, ThreadedServer):
            for c in self.__connections:
                try:
                    if c and c._closed is False:
                        connections.append(c)
                except:
                    pass
            self.__connections = connections
            return connections
        
    def _startRpcSession(self, service):
        '''
        Adds a new session for a connecting client with a persistent connection
        :param service: A py:class::freedm.daemon.service.ClientService
        :returns: session
        :rtype: dict
        '''
        if not service.id in self.__sessions.keys():
            self.__sessions.update({service.id: service._conn})
            return self.__sessions[service.id]
        else:
            return None
        
    def _getRpcSession(self, service):
        '''
        Returns an existing session for a persistently connected client
        :param service: A py:class::freedm.daemon.service.ClientService
        :returns: session
        :rtype: dict
        '''
        try:
            return self.__sessions[service.id]
        except:
            return None
        
    def _terminateRpcSession(self, service):
        '''
        Clears all current sessions of clients with persistent connections
        '''
        try:
            self.__sessions[service.id].close()
        except:
            pass
        
    def _clearRpcSessions(self):
        '''
        Clears all current sessions of clients with persistent connections
        '''
        try:
            for s in self.__sessions.keys():
                # Close all current connections
                try:
                    self.__sessions[s].close()
                except:
                    pass
        finally:
            self.__sessions = {}
        
    def onRpcConnect(self):
        ''' 
        An abstract function executed on RPC client connections. Overwrite this method if needed
        '''
        if self.__class__.__name__ != 'GenericDaemon':
            raise NotImplementedError
    
    def onRpcDisconnect(self):
        ''' 
        An abstract function executed on RPC client disconnections. Overwrite this method if needed
        '''
        if self.__class__.__name__ != 'GenericDaemon':
            raise NotImplementedError
    
    def onDaemonStart(self):
        ''' 
        An abstract function executed after the daemon started. Overwrite this method to implement 
        your daemon logic
        '''
        if self.__class__.__name__ != 'GenericDaemon':
            raise NotImplementedError(f'Class "{self.__class__.__name__}" requires an implementation of function "onDaemonStart"')
    
    def onDaemonHalt(self):
        ''' 
        An abstract function executed before the daemon is shutdown. Overwrite this method to implement 
        your daemon logic
        '''
        if self.__class__.__name__ != 'GenericDaemon':
            raise NotImplementedError(f'Class "{self.__class__.__name__}" requires an implementation of function "onDaemonHalt"')
    
    def notifyRpcClient(self, client, message):
        ''' 
        Output a message to the client
        :param client: A specific py:class::rpyc.core.protocol.Connection
        :param str message: The message text
        '''
        try:
            client.root.printMessage(message)
        except:
            self.logger.debug(f'Could not send message to client ({message[0:50]})')
                
    def _stopDaemon(self):
        '''
        Halts this daemon instance and its subthreads, disconnecting all clients and unbinding from the socket
        '''
        self.logger.info('Halting free.dm {} daemon at {}:{}...'.format(
            self.role.capitalize(),
            self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
            self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port')
            ))
        
        # Execute custom daemon procedures before we shutdown the daemon
        try:
            self.onDaemonHalt()
        except Exception as e:
            self.logger.warn(f'Error when halting {self.role.capitalize()} daemon ({e})')
        
        # Notify active clients about daemon halt
        try:
            for c in self._getRpcConnections():
                self.notifyRpcClient(c, f'{self.role.capitalize()} daemon stopped')
        except:
            pass
        
        # Disconnect all persistent client sessions
        self._clearRpcSessions()
        
        # Tell the DataManager to sync and release all its filesystem handles
        try:
            self.data.sync()
        except Exception as e:
            self.logger.warn(f'{self.role.capitalize()} daemon could not sync back its data ({e})')
        finally:
            self.data.release()

        # Finally stop the server (disconnects all open RPC sessions)
        try:
            self.state = 'idle'
            self.close()
        except:
            self.logger.warn('Could not properly stop free.dm {} daemon at {}:{}...'.format(
                self.role.capitalize(),
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port')
                ))
        # Make sure we really set the idle state in any case!
        finally:
            self.state = 'idle'
            
    def _accept_method(self, sock):
        '''
        Overridden class method for pre-connection checks. While authentication should be handled
        by RPyC's :function:_authenticate_and_serve_client:, we save opening another thread by intercepting 
        a connection at this point if certain daemon states should not allow any further connection.
        '''
        if self.state in ('stopping', 'idle', 'crashed'):
            # Close the socket immediately because daemon is halting or already halted.
            sock.close()
        else:
            # Call the overriden function
            super()._accept_method(sock)
        
    def _spawnDaemon(self):        
        '''
        Spawns this daemon server instance listening to RPC requests
        '''
        self.logger.info('Starting free.dm {} daemon at {}:{}...'.format(
            self.role.capitalize(),
            self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
            self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port')
            ))
        
        # Indicate the new state
        self.state = 'starting'
        
        # Start the daemon watchdog sub-thread which observes the daemon state and can halt the daemon
        def watchdog():
            while True:
                if self.state == 'stopping':
                    self._stopDaemon()
                    break
                elif self.state == 'idle' or (hasattr(self, '_closed') and self._closed):
                    # Just stop this loop if the daemon got stopped
                    break
                else:
                    # We periodically check for the server's state
                    time.sleep(1)
            
        self.__subthreads['watchdog'] = Thread(target=watchdog, name='watchdog')
        self.__subthreads['watchdog'].start()
        
        # A custom authenticator method checking if a client can connect
        def authentication(sock):
            #sock.close()
            #raise AuthenticationError('Authentication error')
        
            #TODO: Implement authentication
            #HIER AUCH WEITERMACHEN...DAEMON() muss eigene auth implementieren oder per Konfiguration übergeben werden?!
            # Wir müssen sicherstellen, dass niemand selber einen CLient entwickelt und API commands absetzt oder WORKS query macht
            #TODO: KÖNNEN WIR SICHERSTELLEN; DASS DER RPyC SOCKET nur von einem bestimmten Nutzer geöffnet werden kann?
            
            return sock, None
        
        # Reference this server instance as global parameter of the service class to enable control of the server via the service's exposed rpc methods
        self.__rpc.update({'__daemon': self})

        # Define a rpyc.Service class with the exposed methods set by the @rpcmethod decorator and reset the __rpc variable
        service = type(f'{self.__class__.__name__}Service', (DaemonService,), self.__rpc)
        self.__rpc = {} # Reset
        
        # Define connection properties (aka as RPyC protocol)
        protocol = {
            # We want that public attributes of RPyC netref objects are accessible
            'allow_public_attrs': True,
            'include_local_traceback': G.MODE == 'debug'
            #'allow_all_attrs':  True,
            #'allow_setattr':    True,
            #'allow_delattr':    True
            }
        
        # Init the RPyC server: Set the dynamically defined service class, address, port and connection properties
        try:
            super().__init__(
                service,
                hostname = self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                port = self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port'),
                ipv6 = False,
                protocol_config = protocol,
                authenticator = authentication,
                logger = self.logger
                )
        except Exception as e:
            self.logger.critical(f'Could not init free.dm {self.role.capitalize()} daemon class ({e})')
            self.close()
            self.state = 'crashed'
            return
        
        # Execute custom daemon startup procedures
        try:
            self.onDaemonStart()
        except KeyboardInterrupt:
            print('')
            self.logger.warn('Keyboard interrupt!')
            self.logger.info(f'{self.role.capitalize()} daemon startup aborted by user')
            self.close()
            self._stopDaemon()
            print(f'{self.role.capitalize()} daemon stopped')
            return
        except Exception as e:
            self.logger.critical(f'Error when starting up free.dm {self.role.capitalize()} daemon ({e})')
            self.state = 'crashed'
            self.close()
            return
        
        # Start the RPyC server
        try:
            # Update state
            self.state = 'running'
            
            # Set the uptime timestamp
            self.setServerValue('uptime', time.time())
            
            # Start the RPyC server (Triggers a blocking thread until it gets closed)
            print(f'{self.role.capitalize()} daemon started')
            self.start()
            
            # Halting the daemon: Check before this program closes -> Detect if the the daemon has properly 
            # halted before and custom shutdown procedures already been executed. If not, do so once more!
            if self.state != 'idle':
                self._stopDaemon()
            print(f'{self.role.capitalize()} daemon stopped')
        except Exception as e:
            self.state = 'crashed'
            self.logger.critical('Could not start free.dm {} daemon at {}:{}...({})'.format(
                self.role.capitalize(),
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port'),
                e
                ))
            self.close()


# DAEMON HOWTO:
#
# - prevent core dumps (many daemons run as root, and core dumps can contain sensitive information)
# - behave correctly inside a chroot gaol
# - set UID, GID, working directory, umask, and other process parameters appropriately for the use case
# - relinquish elevated suid, sgid privileges
# - close all open file descriptors, with exclusions depending on the use case
# - behave correctly if started inside an already-detached context, such as init, inetd, etc.
# - set up signal handlers for sensible daemon behaviour, but also with specific handlers determined by the use case
# - redirect the standard streams stdin, stdout, stderr since a daemon process no longer has a controlling terminal
# - handle a PID file as a cooperative advisory lock, which is a whole can of worms in itself with many contradictory but valid ways to behave
# - allow proper cleanup when the process is terminated
# - actually become a daemon process without leading to zombies
# - Detach the process into its own process group.
# - Set process environment appropriate for running inside a chroot.
# - Renounce suid and sgid privileges.
# - Close all open file descriptors.
# - Change the working directory, uid, gid, and umask.
# - Set appropriate signal handlers.
# - Open new file descriptors for stdin, stdout, and stderr.
# - Manage a specified PID lock file.
# - Register cleanup functions for at-exit processing.
        
