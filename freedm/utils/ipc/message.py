'''
This module defines an IPC server message object and
IPC API commands
@author: Thomas Wanderer
'''

# Imports
from collections import namedtuple


Message = namedtuple('Message',
    '''
    data
    sender
    '''
    )