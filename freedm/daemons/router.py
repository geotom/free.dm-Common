'''
The free.dm Router daemon.
@author: tommi
'''

# free.dm Imports
from freedm.daemons.daemon import GenericDaemon

class RouterDaemon(GenericDaemon):
    '''
    The free.dm Router manages a local router system OS.
    It connects and communicates with a free.dm Server.
    '''
    
    _role = 'router'
    
    _port = 4510
    
    # Init
    def __init__(self):
        # Call the parent __init__ method on creation
        super().__init__()
        
    @GenericDaemon.rid.getter
    def rid(self):
        return 'RID=???'