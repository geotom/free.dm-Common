'''
This module defines a generic IPC API to be used with ICP servers and clients
Subclass from this class to create a custom IPC API for servers and clients.
@author: Thomas Wanderer
'''


class API(object):
    
    version: None
    
    def supports(self):
        pass