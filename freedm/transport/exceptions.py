'''
This module defines module related custom exceptions based on
the freedmBaseException
@author: Thomas Wanderer
'''

# Imports
from freedm.utils.exceptions import freedmBaseException


class freedmSocketCreation(freedmBaseException):
    '''
    Gets thrown when the transport module cannot create a socket
    '''
    template = 'Cannot create transport socket ({error})'
    
    
class freedmSocketShutdown(freedmBaseException):
    '''
    Gets thrown when the transport module cannot remove a socket
    '''
    template = 'Cannot close transport socket ({error})'
    

class freedmMessageWriter(freedmBaseException):
    '''
    Gets thrown when the transport module cannot send a message
    '''
    template = 'Cannot write message to transport connection ({error})'
    

class freedmMessageReader(freedmBaseException):
    '''
    Gets thrown when the transport module cannot read and message
    '''
    template = 'Cannot read message from transport connection ({error})'
    
    
class freedmMessageHandler(freedmBaseException):
    '''
    Gets thrown when the transport message handler creates an exception
    '''
    template = 'Transport message handler failed ({error})'
    
    
class freedmMessageLimitOverrun(freedmBaseException):
    '''
    Gets thrown when the transport socket receives/sends a message exceeding the limit set
    '''
    template = 'Transport message length exceeds limit set ({error})'