'''
This module provides data and configuration management
@author: Thomas Wanderer
'''

# Imports
import os
import logging
from pathlib import Path
from typing import ItemsView, Optional, Union, List, Dict, Any, Type
from logging import Logger

# free.dm Imports
from freedm import models
from freedm.data.store import DataStore
from freedm.data.object import DataObject
from freedm.utils.aio import runConcurrently
from freedm.utils.types import TypeChecker as checker


class DataManager(object):
    '''
    This class acts as central data management facility for all kind of application data 
    (configurations, ephemeral run-time values, cached data structures). It manages a set of uniquely named 
    py:class::freedm.utils.config.DataStore backends. The folder is the default location in which
    all data store backends (files, databases, etc.) reside.
    The manager keeps track of changes and provides a getter/setter interface for all kind of data.
    
    :param str path: A file system location (folder)
    
    The hierarchy of the data management looks as following:
    
    DataManager (Path: ./config/)
    |
    |-- DataStore ("Config", Persistent: True, Type: 'IniStore')
    |   |
    |   |-- DataObject ("daemon", Backend: ./config/daemon.config)
    |   |
    |   |-- DataObject ("freedm", Backend: ./config/freedm.config)
    |
    |-- DataStore ("Cache", Persistent: False, Type: 'MemoryStore')
    |   |
    |   |-- DataObject ("run", Backend: Dictinary in Memory)
    |
    |-- DataStore ("Media", Persistent: True, Type: 'SQLiteStore')
        |
        |-- DataObject ("movies", Backend: ./config/media.sqlite#movies)
        |
        |-- DataObject ("music", Backend: ./config/media.sqlite#music)
    
    A data getter() call would be mapped in the following way:
    
    DataManager.getConfig('daemon.general.version')
    |
    |-- getConfig() would select the DataStore with the alias "config"
        |
        |-- The domain "daemon" distinguishes the DataObject (in this case an INI type file named "daemon.config")
            |
            |-- "general.version" is the data key, representing the value "version" in the INI file category "general"
        
    The automatically created getter/setter methods distinguish which data store to use, thus which
    storage type is utilized while the DataObjects are responsible for accessing the data values
    in a unified way.
    
    The hierarchical abstraction of the data management allows a variety of individual implementations.
    There's no default data store set up by the data manager, so any further store needs to be configured 
    and registered to this data manager. Use any default py:class::freedm.utils.config.DataStore subclass 
    or subclass your own store. The freedm data module ships default data stores for storing ephemeral data 
    values in memory or persistent data to INI or JSON files as well as SQLite databases.
    '''
    
    # The collection of all data objects differentiated by categories: configurations, cached data or volatile run time data
    __stores = {}
    @property
    def stores(self) -> ItemsView:
        return self.__stores.items()

    __path = Path('./config/').resolve()
    @property
    def path(self) -> Path:
        '''The filesystem storage location represented by this class instance'''
        return self.__path
    
    @property
    def logger(self) -> Logger:
        '''The logger of this class'''
        return logging.getLogger(str(os.getpid()))
    
    # Init
    def __init__(self, path: Union[str, Path]=None):
        try:
            # Set the data location
            if path is not None:
                # Make sure we work with an absolute path
                path = Path(path).resolve() if checker.isString(path) else path
                # Check path availability
                if path is False:
                    pass
                elif os.path.exists(path) and os.path.isdir(path) and os.access(path, os.W_OK):
                    self.__path = path
                else:
                    self.logger.critical(f'Cannot access provided storage path "{path}"')
            else:
                if not os.path.exists(self.__path) or not os.path.isdir(self.__path) or not os.access(self.__path, os.W_OK):
                    self.logger.critical(f'Cannot access default storage path "{self.__path}"')
                    
        except Exception as e:
            self.logger.warn(f'Failed to initialize DataManager ({e})')
        self.logger.debug(f'Using data storage location "{self.__path}"')
        
    # Representation
    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.path}>'
                
    # Auto-create Setters & Getters for each registered data store
    def __updateSettersGetters(self) -> None:
        '''
        Creates or removes getter/setter methods on the data manager for each registered store
        '''
        # First remove any obsolete getters & setters ...
        attrs = vars(self)
        obsolete = []
        for v in attrs.keys():
            if (v.startswith('get') or v.startswith('set')) and checker.isFunction(attrs[v]):
                try:
                    self.__stores[v[3:]]
                except:
                    obsolete.append(v)
        for o in obsolete:
            delattr(self, o)
            
        # ... then add getters & setters for all current stores
        created = []
        for alias in self.__stores:
            # Create Getter & Setter
            if not hasattr(self, f'get{alias}') and not hasattr(self, f'set{alias}'):
                setattr(self, f'get{alias}', lambda token, default=None, store=alias: self.__getStoreValue(token, default, store))
                setattr(self, f'set{alias}', lambda token, value=None, store=alias: self.__setStoreValue(token, value, store))
                created.append(alias)

        # Log is we created setter/getter
        for c in created:
            self.logger.debug(f'Added data getters & setters for store "{self.__stores[c]}" (Use "get{c}" & "set{c}" for access)')

    # Store lookup
    def _getStore(self, store: str) -> Optional[Type[DataStore]]:
        '''
        This method returns the required DataStore identified by its alias or ``None`` if the store has not 
        been registered in this DataManager.
        :param str store: The store's alias
        :returns: The data store
        :rtype: py:class::freedm.data.objects.DataStore
        '''
        # Get the proper store alias
        try:
            store = store.lower().capitalize()
        except Exception as e:
            self.logger.warn(f'Invalid store alias "{store}" ({e})')
        
        # Return the data store
        try:
            store = self.__stores[store]
            if isinstance(store, DataStore):
                return store
            else:
                self.logger.warning(f'Store "{store}" is not a proper data store instance')
                return None
        except Exception:
            self.logger.warning(f'Store "{store}" is not registered')
            return None
        
    def getStores(self) -> List[Type[DataStore]]:
        '''
        Returns a list of currently registered stores
        :returns: A list of store instances
        :rtype: [py:class::freedm.data.objects.DataStore]
        '''
        return [store for _, store in self.stores]
    
    # DataStore registration
    def registerStore(self, store: Union[Dict[str, Any], Type[DataStore]]) -> bool:
        '''
        Registers a data store to the manager
        :param [dict/py:class::freedm.data.objects.DataStore] store: The data store or a configuration dictionary
        :returns: ``True`` if the store could be registered
        :rtype: bool
        '''
        # Check store
        if(checker.isDict(store)):
            try:
                store = DataStore(**store)
            except TypeError as e:
                self.logger.warn(f'Cannot create data store instance from invalid parameters ({e})')
        elif not isinstance(store, DataStore):
            self.logger.warn(f'Cannot register invalid store class "{store}" in data manager "{self}"')
            
        # Add store
        if not store.alias in self.__stores.keys():
            # Add the store and set the store's path if empty
            self.__stores[store.alias] = store
            if store.path is None:
                store.path = self.path
                # Warn the user from registering same-type stores with the same path
                if len(self.__stores) >= 2:
                    self.logger.warn(f'Registered store uses "{self.path}". Beware of registering same-type stores with an equal path')
            # Update setters & getters
            self.__updateSettersGetters()
            self.logger.debug(f'Registered data store "{store}" in data manager "{self}"')
            return True
        else:
            self.logger.warn(f'Cannot register a store with name "{store.alias}" twice in data manager "{self}"')
        # If store could not be registered
        return False
        
    # DataStore registration
    def unregisterStore(self, store: Union[str, Type[DataStore]]) -> bool:
        '''
        Unregisters a data store from the manager
        :param [str/py:class::freedm.data.objects.DataStore] store: The data store instance or its alias
        :returns: ``True`` if the store could be unregistered
        :rtype: bool
        '''
        # Check store
        if(isinstance(store, str)):
            alias = store.lower().capitalize()
        elif not isinstance(store, DataStore):
            self.logger.warn(f'Cannot unregister invalid store class "{store}" from data manager "{self}"')
        else:
            alias = store.alias
            
        # Remove store
        if alias in self.__stores.keys():
            store = self.__stores[alias]
            # Tell the store to sync before we remove it
            store.sync()
            # Remove the store and update setters & getters
            del self.__stores[store.alias]
            self.__updateSettersGetters()
            self.logger.debug(f'Unregistered data store "{alias}" from data manager "{self}"')
            return True
        else:
            self.logger.warn(f'Data store "{alias}" not registered in data manager "{self}"')
        # If store could not be unregistered
        return False
        
    def sync(self, store: str=None) -> None:
        '''
        The data manager will tell the specific store (if provided) or all its stores to write 
        back it's data to their data object backends.
        '''
        # Find all stores and data objects to sync
        self.logger.debug(f'Syncing persistent data store "{store}" backends...' if store else 'Syncing all persistent data store backends...')
        for k,s in (None, self._getStore(store),) if store else self.stores:
            s.sync()
    
    def release(self) -> None:
        '''
        Tells each data store to close & release its filesystem handles
        '''
        # Possible errrors
        errors = []
        
        # Find all stores
        self.logger.debug('Releasing data store backends...')
        
        # Create release function
        def storeReleaser(store, errors):
            try:
                store.releaseHandle()
            except Exception as e:
                errors.append((store, e))
         
        # Release stores concurrently    
        runConcurrently(storeReleaser, self.getStores(), errors)
                          
        # Report any errors
        for e in errors:
            self.logger.warn(f'Data store "{e[0]}" could not release its filesystem handle ({e[1]})')
        
    def __setStoreValue(self, token: str, value: Any=None, store: str=None) -> bool:
        '''
        Adds/Updates a data value in the provided store under its provided key token.
        Key tokens are alphanumeric keys separated by dots ("."). Tokens also support numeric IDs to
        set data of collections (lists) or an object of ID referenced items.
        
        Example:
        
        "user.45.name" corresponds to the name of user 45 in a dictionary with the following structure:
            {"user": {"45": {"name": "User A"}, "46": {"name": "User B"}, ...}}
            
        "user.[].name" adds a new user object with name attribute in a dictionary with the following structure:
            {"user": {"45": {"name": "User A"}, "46": {"name": "User B"}, ...}}
            
        "settings.options.2" corresponds to the 2nd option entry (= "No") in a dictionary/list with the 
        following structure:
            {"settings": {"options": ["Yes", "No", "Maybe", "Never"]}}
            
        "settings.options.[]" adds a new option entry to a dictionary/list with the 
        following structure:
            {"settings": {"options": ["Yes", "No", "Maybe", "Never"]}}
        :param str token: The key token
        :param value: Any serializable value to store
        :param str store: The store alias
        :returns: ``True`` if the value could be set
        :rtype: bool
        '''
        # Get the data store
        store = self._getStore(store)
            
        # Set the value
        try:
            if store: return store.setValue(token, value)
        except Exception as e:
            self.logger.warn(f'Writing of new value "{token}={value}" failed ({e})')
            return False
        
    def __getStoreValue(self, token: str, default: Any=None, store: str=None) -> Any:
        '''
        Returns a data value from the provided store looked up by its provided key token.
        Key tokens are alphanumeric keys separated by dots ("."). Tokens also support numeric IDs to
        set data of collections (lists) or an object of ID referenced items.
        
        "user.45.name" corresponds to the name of user 45 in a dictionary with the following structures:
            {"user": {45: {"name": "User A"}, 46: {"name": "User B"}, ...}}
            {"user": {"45": {"name": "User A"}, "46": {"name": "User B"}, ...}}
            {"user": [...44th..., {"name": "User A"}, ...46th...]}
            
        "user.[].name" corresponds to the names of all users in a dictionary with the following structures:
            {"user": {45: {"name": "User A"}, 46: {"name": "User B"}, ...}}
            {"user": {"45": {"name": "User A"}, "46": {"name": "User B"}, ...}}
            {"user": [..., {"name": "User A"}, {"name": "User B"}, ...]}
            
        "settings.options.2" corresponds to the 2nd option entry (= "No") in a list with the 
        following structure:
            {"settings": {"options": ["Yes", "No", "Maybe", "Never"]}}
            
        "settings.options.[].alias" corresponds to all option aliases in a list with the 
        following structure - Do not use "[]" at the end of your token as "settings.options.[]" means the same 
        as "settings.options".
            {"settings": {"options": [{"alias": "Yes", "value": True}, {"alias": "No", "value": False}]}}
            
        Wildcard support is achieved by the key "+". It retrieves a list of all data-structures, regardless
        if it is a list or dictionary.
           
        "settings.+.ports" corresponds to an array with the ports of all sub-elements of settings
        following structure:
            {"settings": {"samba": {"port": 1}, "postfix": {"port": 995}, "ssh": {"port": 22}}
            
        :param str token: The key token
        :param object default: An optional alternative value to return instead if the first value cannot be retrieved.
        If the provided token and alternative value both represent the same string, this method will automatically 
        look up and replace the alternative value with the token's default value.
        :param str store: The store alias
        :returns: The corresponding value or ``None`` if not found
        '''
        # Get the data store
        store = self._getStore(store)
        
        # Get the value
        try:
            if store: return store.getValue(token, default)
        except Exception as e:
            self.logger.info(f'Value "{token}" lookup failed ({e})')
            # The default return if the token's value cannot be found
            if default is not None:
                if default == token:
                    default = models.getDefaultValue(token)
                else:
                    default = models.getValidatedValue(token, default)
                if default is not None:
                    self.logger.info(f'Value "{token}" lookup failed. Using default value "{default}"')
        return default