'''
This module defines the base IPC server. 
Subclass from this class to create a custom IPC server implementation.
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    from typing import TypeVar
    
    # free.dm Imports
    from freedm.utils.async import getLoop
    from freedm.utils.exceptions import freedmBaseException
    from freedm.utils.ipc.message import Message
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


IC = TypeVar('IC', bound='IPCSocketClient')


class IPCSocketClient(object):
    '''
    A generic client implementation to connect to IPC servers.
    '''