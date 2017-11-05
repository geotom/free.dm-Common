'''
The generic node daemon class based on the generic daemon implementation.
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
    this class to implement specific node roles.
    '''
    
    _role = 'node'

    _id = 0
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