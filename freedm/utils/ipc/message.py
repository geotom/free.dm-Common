'''
This module defines an IPC server message object and
IPC API commands
@author: Thomas Wanderer
'''

# Imports
from enum import Enum
from collections import namedtuple
from typing import Optional, Any, Union, TypeVar


C = TypeVar('C', bound='CommandMessage')


class CommandMessage(Enum):
    PING=1
    PONG=2
    SET_STREAM = 3
    SET_DATA = 4
    
    @classmethod
    def supports(cls, value: Any) -> bool:
        return any(value == item.value for item in cls)
    
    @classmethod
    def get(cls, value: Any) -> Optional[Union[C]]:
        for item in cls:
            if item.value == value: return item
        return None


Message = namedtuple('Message',
    '''
    data
    sender
    '''
    )