'''
This module defines an IPC server communicating via TCP
@author: Thomas Wanderer
'''

try:
    # Imports
    import asyncio
    import time
    from typing import TypeVar
    
    # free.dm Imports
    from freedm.utils.ipc.server.base import IPCSocketServer
    from freedm.utils.ipc.exceptions import freedmIPCSocketCreation
    from freedm.utils.ipc.connection import Connection, ConnectionType
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


TS = TypeVar('TS', bound='TCPSocketServer')


class TCPSocketServer(object):
    '''
    '''
    # https://www.pythonsheets.com/notes/python-socket.html
    # http://asyncio.readthedocs.io/en/latest/tcp_echo.html
    
#     addr = writer.get_extra_info('peername')
#     print("Received %r from %r" % (message, addr))

    # Mit IP6 oder nicht?
    # https://www.pythonsheets.com/notes/python-socket.html#simple-tcp-echo-server-through-ipv6
    # https://www.pythonsheets.com/notes/python-socket.html#disable-ipv6-only
    # 