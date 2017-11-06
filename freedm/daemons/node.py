'''
The generic node daemon class uses the generic daemon implementation.
A node daemon introduces certain properties and methods enabling it to 
function as free.dm node daemon.
@author: Thomas Wanderer
'''

# free.dm Imports
from freedm.daemons.daemon import GenericDaemon
from freedm.data.objects import DatabaseStore
from freedm.utils.types import TypeChecker as checker

class NodeDaemon(GenericDaemon):
    '''
    A free.dm NodeDaemon is a generic node in the free.dm network,
    participating in communication and offering services. Inherit from 
    this class to implement specific free.dm node roles.
    '''
    
    _role : str = 'node'

    _id : int = 0
    @property
    def id(self):
        '''The node id serves as address for inter-node communication'''
        return self._id
    @id.setter
    def id(self, id):
        if checker.isInteger(id):
            self._id = id
            
    # Representation
    def __repr__(self):
        return '<{}@{}:{} (ID: {}, Process: {})>'.format(
            self.__class__.__name__,
            self.data.getConfig('daemon.rpc.address', 'daemon.rpc.address'),
            self.data.getConfig('daemon.rpc.port', 'daemon.rpc.port'),
            self.id,
            self.pid
            )
    
    def onRpcConnect(self):
        print('...A client connected')
        
    def onRpcDisconnect(self):
        print('...A client disconnected')
        
    def handleEvent(self, event, *args, **kwargs):
        '''
        '''
        # TODO: Implement an async method triggering direct daemon actions or invoking workers
        # The events should be queued (one for the daemon or worker wise?) but executed asynchronously!
        pass
    
    def emitEvent(self, event, callback):
        '''
        '''
        # TODO: Implement an async method sending events. This should not be blocked by active workers or handling incoming events!
        # The emitting of events should also work asynchronously to make sure we can execute the callback
        pass