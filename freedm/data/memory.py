'''
This module provides a DataStore based on in-memory dictionaries.
@author: Thomas Wanderer
'''

# free.dm Imports
from freedm.data.store import DataStore
from freedm.data.object import DataObject
from typing import Union, Any, Type


class MemoryStore(DataStore):
    '''
    A data store which reads and writes its data simply to a dictionary in the memory.
    The token has no length/depth limit as every new token get mapped to a new dictionary.
    '''
    # Attributes
    _persistent: bool = False
    _writable: bool = True
    _default_name: str = 'Cache'
    _default_filetype: str = ''
    description: str = 'An ephemeral memory store'
    
    # Set up the Memory store
    def __init__(self, *args, **kwargs):
        '''
        Just sets the path to something else to avoid a warning
        '''
        # Init the store
        super().__init__(*args, **kwargs)
        # Set the path to "False" so this store never gets a path configured by a data manager
        self.path = False
    
    # Implement data setters & getter
    def _setRaw(self, domain: Type[DataObject], token: str, value: Any) -> None:
        return None
    
    def _getRaw(self, domain: Type[DataObject], token: str) -> Any:
        return None
    
    # Implement domain loading and unloading
    def _loadDomain(self, domain: str, path: str) -> None:
        return DataObject()
        
    def _unloadDomain(self, domain: str, path: str) -> None:
        if domain in self._data:
            del self._data[domain]
    
    def _syncDomain(self, domain: Type[DataObject], path: str) -> None:
        domain.clearTainted()
    
    def releaseHandle(self) -> None:
        pass