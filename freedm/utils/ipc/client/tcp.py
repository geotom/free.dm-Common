'''
This module defines an IPC client communicating via TCP sockets
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    from typing import TypeVar
    
    # free.dm Imports
    from freedm.utils.ipc.client.base import IPCSocketClient
    from freedm.utils.exceptions import freedmBaseException
    from freedm.utils.ipc.message import Message
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


UC = TypeVar('UC', bound='TCPSocketClient')


class TCPSocketClient(IPCSocketClient):
    '''
    An IPC client connecting to IPC servers via an TCP socket.
    '''
    
    # For making a connection
    '''
    Asking getaddrinfo() About Services
    https://erlerobotics.gitbooks.io/erle-robotics-python-gitbook-free/socket_names_and_dns/asking_getaddrinfo_about_services.html
    '''