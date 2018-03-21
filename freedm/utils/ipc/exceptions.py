'''
This module defines module related custom exceptions based on
the freedmBaseException
@author: Thomas Wanderer
'''

# Imports
from freedm.utils.exceptions import freedmBaseException


class freedmIPCSocketCreation(freedmBaseException):
    '''
    Gets thrown when the IPC socket module cannot create a socket
    '''
    template = 'Cannot create IPC socket ({error})'
    
    
class freedmIPCSocketShutdown(freedmBaseException):
    '''
    Gets thrown when the IPC socket module cannot remove a socket
    '''
    template = 'Cannot close IPC socket ({error})'
    

class freedmIPCMessageWriter(freedmBaseException):
    '''
    Gets thrown when the IPC socket module cannot send a message
    '''
    template = 'Cannot write message to IPC connection ({error})'
    

class freedmIPCMessageReader(freedmBaseException):
    '''
    Gets thrown when the IPC socket module cannot read and message
    '''
    template = 'Cannot read message from IPC connection ({error})'
    
    
class freedmIPCMessageHandler(freedmBaseException):
    '''
    Gets thrown when the IPC message handler creates an exception
    '''
    template = 'IPC message handler failed ({error})'
    
    
class freedmIPCMessageLimitOverrun(freedmBaseException):
    '''
    Gets thrown when the IPC socket receives/sends a message exceeding the limit set
    '''
    template = 'IPC message length exceeds limit set ({error})'