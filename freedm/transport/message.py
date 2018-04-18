'''
This module defines a message object received by transport sockets
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