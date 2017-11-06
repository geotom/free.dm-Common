'''
The generic RPC client class to establish communication with free.dm daemons
@author: Thomas Wanderer
'''

# Imports
import rpyc

# free.dm Imports
from freedm.utils import logger as L
from freedm.utils import globals as G
from freedm.data.objects import DataManager, IniFileStore
from freedm.utils.types import TypeChecker as checker
from freedm.daemons.service import ClientService

class DaemonClient(object):
    
    __connection = None
    
    _exception = None
        
    __data = None
    @property
    def data(self):
        '''The path used by this class'''
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
            
    @property
    def connected(self):
        '''Shows if a connection is established'''
        if checker.isExactType(self.__connection, 'rpyc.core.protocol.Connection'):
            if hasattr(self.__connection, '_closed'):
                if self.__connection._channel:
                    return self.__connection._channel.stream.closed is not True
                else:
                    return False
            else:
                return False
        else:
            return False
    
    # Init
    def __init__(self, data=None, logger=None, persistent=False):
        # Set logger & data manager
        self.data = data
        self.logger = logger
        
        # Add the default configuration store to data manager
        self.data.registerStore(
            IniFileStore(
                **{
                    'name': 'Configuration',
                    'alias': 'config',
                    'filetype': 'config',
                    'synced': False
                    }
                )
            )
        
        # Try connecting to a running daemon instance on creation
        self.connect(persistent)
    
    def connect(self, persistent=False):
        '''
        Tries to establish a connection to a running free.dm Server instance
        :param bool persistent: Set to ’’True’’ to keep the connection alive
        '''
        if not self.connected:
            protocol = {
                # We want that public attributes of RPyC netref objects are accessible
                'allow_public_attrs': True,
                'include_local_traceback': G.MODE == 'debug',
                'propagate_KeyboardInterrupt_locally': True,
                'propagate_SystemExit_locally': True
                }
            try:
                self._exception = None # Reset
                self.__connection = rpyc.connect(
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                    self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port'),
                    config=protocol,
                    service=ClientService
                    )
                self.logger.debug('Established connection to daemon on {}:{}'.format(
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                    self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port')
                    ))
            except Exception as e:
                self._exception = e
                self.logger.debug('Cannot connect to daemon on {}:{}'.format(
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                    self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port')
                    ))
            
            # Keep this connection alive and do not return 
            if self.__connection and persistent:
                try:
                    r = rpyc.async(self.__connection.root.keepalive)()
                    r.wait()
                    print('Connection reset by peer')
                except KeyboardInterrupt:
                    print('\nConnection reset by user')
                except EOFError:
                    print('Connection reset by peer')
                except:
                    print('Connection crashed')

    def disconnect(self):
        '''
        Disconnects an established connection to a running free.dm Server instance
        '''
        if self.connected:
            try:
                self.__connection.close()
                self.__connection = None
            except Exception:
                self.logger.warn('Cannot disconnect from daemon on {}:{}'.format(
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                    self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port')
                    ))
        else:
            self.logger.debug('Not connected to daemon on {}:{}'.format(
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port')
                ))
            
    def stopDaemon(self):
        '''
        Tells the daemon to halt and client disconnect from it.
        The client then awaits until the daemon really stopped by checking
        if the daemon still runs and outputs messages up to a maximum timeout of 60 seconds.
        '''
        if self.connected:
            import time
            from pydoc import locate
            try:
                # Get info about the running daemon
                info = self.__connection.root.exposed_getDaemonInfo()
                role = info.get('role')
                cls = locate(info.get('type'))
                counter = 0
                # Stop daemon & immediately disconnect
                self.__connection.root.stopDaemon(0)
                self.disconnect()
                # Wait until the daemon really stops (For a maximum time of 60 seconds)
                while True:
                    if cls.isRunning():
                        time.sleep(0.5)
                        counter += 0.5
                        if counter == 10:
                            print(f'Waiting for {role} daemon to shutdown...')
                        elif counter == 20:
                            print(f'{role} daemon seems to be still busy...')
                        elif counter == 60:
                            print(f'{role} daemon probably failed to shutdown (still running)')
                            break
                    else:
                        print(f'{role} daemon stopped')
                        break
            except EOFError:
                pass
            except Exception as e:
                self.logger.warn(f'Could not stop {role or "Generic"} daemon ({e})')
                
        else:
            self.logger.debug('Not connected to daemon on {}:{}'.format(
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                ))
    
    def reloadDaemon(self, data=None):
        '''
        Tells the daemon to reload its data configuration. By default the daemon will reload its 
        configured data storage but an alternative data storage can be supplied to the daemon on the fly.
        :param config: The data storage path or py:class:::freedm.data.objects.DataStorage
        '''
        if self.connected:
            try:
                self.__connection.root.reloadDaemon(data)
            except EOFError:
                self.logger.warn('Connection refused by {}:{}'.format(
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                    ))
        else:
            self.logger.debug('Not connected to daemon on {}:{}'.format(
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                ))
                
    def rpcCall(self, rpcmethod, *args, **kwargs):
        '''
        A generic RPC caller that dispatches the call to the RPC daemon
        :param str rpcmethod: The RPC method's name
        '''
        if self.connected:
            if(hasattr(self.__connection.root, rpcmethod)):
                try:
                    return getattr(self.__connection.root, rpcmethod)(*args, **kwargs)
                except EOFError:
                    self.logger.warn('Connection refused by {}:{}'.format(
                        self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                        self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                        ))
            else:
                self.logger.warn('RPC method {} not supported by {}:{}'.format(
                    rpcmethod,
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                    ))
        else:
            self.logger.debug('Not connected to daemon on {}:{}'.format(
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                ))
    
    def queryDaemon(self, query):
        '''
        Sends a query to the daemon and will return the response of the server's API as result
        :param str query: The query parameter
        '''
        if self.connected:
            try:
                self.__connection.root.queryDaemon(query)
            except EOFError:
                self.logger.warn('Connection refused by {}:{1'.format(
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                    ))
        else:
            self.logger.debug('Not connected to daemon on {}:{}'.format(
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                ))
                  
    def getDaemonInfo(self):
        '''
        Sends a query to the daemon and will return the response of the server's API as result
        '''
        if self.connected:
            try:
                import freedm.templates.client
                try:
                    from jinja2 import Template
                except ImportError as e:
                    print('Make sure you have jinja2 installed: pip install jinja2')
                    return
                # Get the daemon info & correct template identifier
                info = self.__connection.root.getSystemInfo()
                template = f'{info["role"]}Info'
                 
                # Import the correct template string
                if hasattr(freedm.templates.client, template):
                    template = getattr(freedm.templates.client, template)
                else:
                    template = freedm.templates.client.DaemonInfo
                
                # Define custom jinja2 methods
                def createTable(columns, rowdata, **kwargs):
                    import collections
                    from freedm.utils.formatters import TableFormatter
                    return TableFormatter(collections.OrderedDict(columns), rowdata, **kwargs).render()
                
                # Create jinja2 Template and add custom methods
                template = Template(template)
                template.globals['createTable'] = createTable
                 
                # Print info obtained from the daemon
                print(template.render(info))
            except EOFError:
                self.logger.warn('Connection refused by {}:{}'.format(
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                    self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                    ))
        else:
            self.logger.debug('Not connected to daemon on {}:{}'.format(
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
                self.data.getConfig('daemon.rpc.address', 'daemon.rpc.port')
                ))
        