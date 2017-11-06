'''
This module provides data and configuration management
@author: Thomas Wanderer
'''

# Imports
import os
import logging
import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# free.dm Imports
from freedm import models
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
    def stores(self):
        return self.__stores.items()

    __path = './config/'
    @property
    def path(self):
        '''The filesystem storage location represented by this class instance'''
        return self.__path
    
    @property
    def logger(self):
        '''The logger of this class'''
        return logging.getLogger(str(os.getpid()))
    
    # Init
    def __init__(self, path=None):
        try:
            # Set the data location
            if path is not None:
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
    def __updateSettersGetters(self):
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
    def _getStore(self, store):
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
        
    def getStores(self):
        '''
        Returns a list of currently registered stores
        :returns: A list of store instances
        :rtype: [py:class::freedm.data.objects.DataStore]
        '''
        return [store for alias, store in self.stores]
    
    # DataStore registration
    def registerStore(self, store):
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
    def unregisterStore(self, store):
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
        
    def sync(self, store=None):
        '''
        The data manager will tell the specific store (if provided) or all its stores to write 
        back it's data to their data object backends.
        '''
        # Find all stores and data objects to sync
        self.logger.debug(f'Syncing persistent data store "{store}" backends...' if store else 'Syncing all persistent data store backends...')
        for k,s in (None, self._getStore(store),) if store else self.stores:
            s.sync()
    
    def release(self):
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
        
    def __setStoreValue(self, token, value=None, store=None):
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
        
    def __getStoreValue(self, token, default=None, store=None):
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

class DataStore(object):
    '''
    This abstract class represents a data category managed by a py:class::freedm.utils.config.DataManager
    It is an either persistent or ephemeral data container, built of one or more thematic data domains
    which are each mapped to py:class::freedm.utils.config.DataObject classes. While the DataStore distinguishes
    the way data is read and written, the DataObject represents a common interface for accessing data values.
    The manager triggers the automatic loading of any data DataObject. A data store can define its own file 
    system location or inherits the location by its parent data manager. Data stores are also responsible for
    loading, unloading and syncing its data objects.
    '''
    # Defaults
    _default_name = 'data'
    _default_filetype = 'cfg'
    
    # Sync strategy
    _sync_parallel = True       # Data domains should be simultaneously synced => True or sequentially => False
    _sync_max_threads = 10      # The max number of parallel sync operations/threads if parallel sync is enabled
    
    @property
    def path(self):
        '''The filesystem storage location represented by this class instance'''
        try:
            return self.__path
        except AttributeError:
            return None
    @path.setter
    def path(self, path):
        if path is not None:
            # First we laboratory if a path has already been set to "False". In this case we set nothing
            try:
                if self.__path is False:
                    return
            except AttributeError:
                pass
            # If we are sure that path is not "False" or has not been set, we continue
            if path is False:
                # We allow setting of value "False", to allow a store to deny getting any path configured (for instance by a DataManager)
                self.__path = False
            elif os.path.exists(path) and os.path.isdir(path) and os.access(path, os.W_OK):
                self.__path = path
            else:
                self.logger.critical(f'Cannot access provided storage path "{path}"')
                
    @property
    def filetype(self):
        '''The filetype (ending .*) used by this store's filesystem based backends'''
        try:
            return self.__filetype
        except AttributeError:
            return self._default_filetype
    @filetype.setter
    def filetype(self, extension):
        if isinstance(extension, str):
            self.__filetype = extension[1:] if extension.startswith('.') else extension
            
    @property
    def alias(self):
        '''The optional alias of the data store. By default the alias is build from the store's name'''
        try:
            return self.__alias if self.__alias is not None else self.name.lower().capitalize()
        except AttributeError:
            return self.name.lower().capitalize()
    @alias.setter
    def alias(self, name):
        if isinstance(name, str) and name.isalpha():
            self.__alias = name.lower().capitalize()
        else:
            raise AttributeError(f'Invalid freedm.data.objects.DataStore alias "{name}". Must be an alphabetical string')
        
    @property
    def name(self):
        '''The store's name. Used to derive the alias of the store if not set separately'''
        try:
            return self.__name if self.__name is not None else self._default_name
        except AttributeError:
            return self._default_name
    @name.setter
    def name(self, name):
        if isinstance(name, str) and name.isalpha():
            self.__name = name
        else:
            raise AttributeError(f'Invalid freedm.data.objects.DataStore name "{name}". Must be an alphabetical string')
    
    # Data persistence: Indicates that data of this store is read from/written to a filesystem or database backend
    _persistent = False
    @property
    def persistent(self):
        return self._persistent
    @persistent.setter
    def persistent(self, mode):
        raise AttributeError('Set this attribute on instancing the store')
    
    # Data write mode: indicates that we can set/unset values. If a store is persistent, it means the store also must be writable
    _writable = True
    @property
    def writable(self):
        return True if self.persistent else self._writable
    @writable.setter
    def writable(self, mode):
        raise AttributeError('Set this attribute on instancing the store')
    
    # Sync mode: Indicates that all data changes are immediately synchronized between backend and dataobject
    _synced = True
    @property
    def synced(self):
        return self._synced
    @synced.setter
    def synced(self, mode):
        raise AttributeError('Set this attribute on instancing the store')
    
    @property
    def logger(self):
        '''The logger of this class'''
        return logging.getLogger(str(os.getpid()))
        
    # Store description
    description = None
        
    # DataObject store
    _data = {}
    
    # An optional IO handle for stores with filesystem backends or persistent socket connections
    _iohandle = None
    
    # Representation
    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.alias}>'
    
    # Init
    def __init__(self, name=None, alias=None, description=None, path=None, filetype=None, writable=None, persistent=None, synced=False):
        '''
        :param str name: An alphabetical name without whitespace characters (Used for setters/getters) 
        :param str alias: An optional alphabetical alias without whitespace characters (Used instead of the name for setters/getters) 
        :param str description: The store description
        :param str path: An optional file system location (folder). Will otherwise be set by the data manager
        :param str filetype: An optional file ending (.*) for file backends used by this store
        :param bool writable: ``True`` if the store is writable
        :param bool persistent: ``True`` if the store should save its data persistently
        :param bool synced: ``True`` if the store should auto-load and auto-sync its backends
        '''
        # Set up the store
        if name is not None:
            self.name = name
        if alias is not None:
            self.alias = alias
        self.description = description
        self.path = path
        self.filetype = filetype
        if isinstance(writable, bool):
            self._writable = writable
        if isinstance(persistent, bool):
            self._persistent = persistent
        if isinstance(synced, bool):
            self._synced = synced
        
        # Plausibility checks
        if not self.writable and self.persistent:
            self.logger.warn(f'Persistent data store "{self.alias}" cannot save data (Configured as non writable)')
                
    # Token dissection
    def __tokenize(self, token):
        '''
        This method dissects a key token into its components representing the domain part and the data key.
        It maps the domain token to a loaded/auto-loaded DataObject (domain) if possible. If not, the returned
        domain will be just a string.
        :param str token: The token
        :returns: The name (string or data object) representing the domain and the tokenized keys
        :rtype: [str/py:class::freedm.data.objects.DataObject]
        '''
        # Return objects
        domain = None
        tokens = None
         
        # Dissect
        try:
            keys = token.split('.', 1)
            # Check if the token has a valid length
            if len(keys) < 1 or keys[0].strip() == '':
                self.logger.warning(f'Invalid data token "{token}" (Too few key tokens)')
            else:
                # Make sure that we set a data object even it is empty (Empty dictionaries evaluate to "False" in Python)
                domain = self.getDomain(keys[0])
                domain = domain if isinstance(domain, DataObject) else keys[0]
                tokens = keys[1] if len(keys) > 1 else ''
        except Exception as e:
            self.logger.warning(f'Could not dissect data token "{token}" ({e})')
         
        # Return the domain part and the key tokens
        return domain, tokens
    
    # Filesystem handles
    def releaseHandle(self):
        '''
        Abstract method to close and release any open IO handle (filesystem/socket).
        Subclasses who open a file or socket should close them safely. On shutdown, 
        this method gets automatically called by the data manager to whom this store 
        instance is registered to.
        '''
        if self._iohandle is not None:
            # Release the IO handle of the store
            try:
                # In case of files and sockets
                self._iohandle.close()
            except:
                # In case of filesystem observer
                self._iohandle.stop()
            finally:
                del self._iohandle
                self._iohandle = None
                
        # Release all IO handles of the store's data domains (Data objects)
        def domainReleaser(domain):
            if domain._iohandle is not None:
                # Release the IO handle of the domain
                try:
                    # In case of files and sockets
                    domain._iohandle.close()
                except:
                    # In case of filesystem observer
                    domain._iohandle.stop()
                finally:
                    del self._iohandle
                    self._iohandle = None
        # Run concurrently
        runConcurrently(domainReleaser, [domain for name, domain in self._data.items()])

    # Value getting and setting
    def setValue(self, token, value):
        '''
        Set the token's value in the DataObject after verifying the value against its schema definition 
        to insure we only set valid values. Otherwise we raise an ValueError exception.
        :param str token: The key token
        :param str token: The value
        :returns: ``True`` if the value could be set
        :rtype: bool
        '''
        # Do some pre-checks (Can we write to store, Is it a correct token, Do we have a value, Is the value valid?=
        try:
            # Check if store is writeable
            if not self.writable:
                raise UserWarning(f'The {"persistent" if self.persistent else "ephemeral"} data store "{self}" is not writable')
            
            # Set the value
            self.logger.debug(f'Setting value "{token}={value}" in data store "{self}"')
            
            # Validate value before we proceed
            if value is not None and models.getValidatedValue(token, value) is None:
                raise UserWarning('Validation error')
            
            # Write the value
            if value is None:
                raise UserWarning('Value is "None"')
        except Exception as e:
            self.logger.warn(f'Setting value "{token}={value}" in data store "{self}" failed ({e})')
            return False
            
        # Get the data domain object (quick lookup attempt, then auto-loading domain)
        try:
            # Try a fast 1st pass immediately accessing the data domain object
            domain, key = token.split('.', 1)
            dataobject = self._data[domain]
        except KeyError:
            # The previous fast attempt did not work. We will now auto-load the domain data backend
            dataobject, key = self.__tokenize(token)
        except ValueError:
            domain = token
            dataobject, key = self.__tokenize(token)
        except:
            pass
        
        # Set the value
        if isinstance(dataobject, DataObject):
            # Set the new value for the key token to the domain data object
            try:
                if dataobject.setValue(key, value):
                    result = True
                    #TODO: We should emit a datachanged event that token "token" has been changed. BUT WAIT. WE SHOULD DO THIS ONLY AFTER WE SYNC IN THE NEXT STEP!!!
                    print(f'TODO: Value "{dataobject._changed[-1]}" changed in store "{self}"')
            except Exception as e:
                result = False
                self.logger.warn(f'Setting value "{token}" to data domain "{domain}" failed ({e})')
            
            # If this store is synced, then also set the raw value immediately
            if result and self.synced and self.persistent:
                try:
                    # Write the new value back to its backend and reset the tainted status of the dataobject
                    if self._setRaw(dataobject, key, value):
                        if key in dataobject._changed:
                            dataobject._changed.remove(key)
                except Exception as e:
                    self.logger.warn(f'Syncing the new value "{token}" to the data object backend "{dataobject._backend}" failed ({e})')   
        else:
            result = False
            self.logger.warn(f'Setting value "{token}" failed. Data domain "{domain}" unavailable')
            
        # Return the result
        return True if result else False
        
    def getValue(self, token, default=None):
        '''
        Looks up the token's value in the corresponding DataObject and verifies the value against its schema definition
        to insure we only return valid values. Otherwise we raise an ValueError exception.
        :param str token: The key token
        :param object default: An optional alternative value returned instead if the value cannot be retrieved.
        If the provided token and default value both represent the same string, this method will automatically 
        look up and replace the default value with the token's default value.
        '''
        # Log
        self.logger.debug(f'Getting value "{token}" from data store "{self}"')
        
        # Set a default value
        value = None
        
        # Make sure token does not end with "[]"
        try:
            token = token[:-3] if token.endswith('.[]') else token
        except:
            self.logger.warn(f'Getting value "{token}" failed (Problem with token)')
            return value
        
        # Get the data domain object (quick lookup attempt, then auto-loading domain)
        try:
            # Try a fast 1st pass immediately accessing the data domain object
            domain, key = token.split('.', 1)
            dataobject = self._data[domain]
        except KeyError:
            # The previous fast attempt did not work. We will now auto-load the domain data backend
            dataobject, key = self.__tokenize(token)
        except ValueError:
            domain = token
            dataobject, key = self.__tokenize(token)
        except:
            pass

        # Get the value (First attempt from the domain's cache, then by trying to load the raw value
        if isinstance(dataobject, DataObject):
            try:
                # First try to get the value from the domain data object
                value = dataobject.getValue(key)
            except LookupError as e:
                # If this fails, then try to get/load the raw value (from the backend)
                try:
                    value = self._getRaw(dataobject, key)
                    
                    # TODO: Should we cache any returned values in the related DataObject, if we receive a raw value from the backend?
                    # if value: ...
                    # !!! STOP!!! HIER NOCH NICHT CACHEN, DA WIR JA ERST SPÄTER mit getValidatedValue VALIDIEREN!
                    # What if the data has changed in the data backend (e.g. database) and we return then the old cached value?
                    # Should we handle this automatically for instance by checking the synced configuration of the store?
                    # Should we be able to set a maximum TimeToLive for cached data and only then we retrieve the data again as rawValue?
                    
                except Exception as e:
                    self.logger.warn(f'Getting value "{token}" from data domain "{domain}" failed ({e})')
            except Exception as e:
                self.logger.warn(f'Getting value "{token}" from data domain "{domain}" failed ({e})')
        else:
            self.logger.warn(f'Getting value "{token}" failed. Data domain "{domain}" unavailable')

        # Use the retrieved value or the provided alternative default value and validate
        if value is not None:
            value = models.getValidatedValue(token, value)
        elif value is None and default is not None:
            if default == token:
                value = models.getDefaultValue(default)
            else:
                value = models.getValidatedValue(token, default)
            if value is not None:
                self.logger.info(f'Getting value "{token}" failed. Using default value "{value}"')
        else:
            self.logger.info(f'Getting value "{token}" failed. Please set or define a default value')
        
        # Return the value
        return value
    
    def _setRaw(self, domain, token, value):
        '''
        Abstract method to store the raw value into a data objects.
        :param py:class::freedm.data.objects.DataObject domain: The domain data object
        :param str token: The key token
        :param object value: The value
        :returns: ``True`` if the value could be set
        :rtype: bool
        '''
        raise NotImplementedError(f'Abstract method _setRaw not implemented in class "{self.__class__.__module__}.{self.__class__.__name__}"')
            
    def _getRaw(self, domain, token):
        '''
        Abstract method to retrieve the raw value from a DataObject.
        :param py:class::freedm.data.objects.DataObject domain: The domain data object
        :param str token: The key token
        :returns: The value
        '''
        raise NotImplementedError(f'Abstract method _getRaw not implemented in class "{self.__class__.__module__}.{self.__class__.__name__}"')
            
    # Data backend loading        
    def getDomain(self, domain):
        '''
        Returns the domain DataObject and tries to auto-load it if not yet done. Each subclass should define its own loading
        implementation as each domain DataStore type will access its data backend differently.
        :param str domain: The data domain
        :returns: The domain DataObject
        :rtype: py:class::freedm.data.objects.DataObject
        '''       
        try:
            # 1st, try an fast attempt, assuming the domain is already loaded
            domain = domain.lower()
            return self._data[domain]
        except:
            # 2nd, when 1st attempt failed load the domain backend first
            if isinstance(domain, str):
                return self.loadDomain(domain)
            else:
                self.logger.warn(f'Invalid data domain "{domain}". Must be a string')
                return None
            
    def loadDomain(self, domain):
        '''
        Loads the domain related DataObject into this store and returns it
        :param str domain: The data domain
        :returns: The domain DataObject
        :rtype: py:class::freedm.data.objects.DataObject
        '''
        try:
            domain = domain.lower()
            self.logger.debug(f'Loading data domain "{domain}" into {"persistent" if self.persistent else "ephemeral"} store "{self}"')
            # Load the domain data from its backend
            dataobject = self._loadDomain(domain, self.path)
            # First evaluate if data object is empty as empty dictionaries evaluate as "False" in Python, otherwise validate the returned domain's data and proceed only if the validation does not fail
            if not dataobject or isinstance(models.getValidatedValue(domain, dataobject), DataObject):
                # 
                if domain in self._data and not self._data[domain].syncing:
                    if domain in self._data:
                        # Calculate the differences between currently set data object and the newly loaded one to emit "datachanged" events
                        # diff = self.getDiff(dataobject)
                        #TODO: Calculate difference
                        print('TODO: DOMAIN ALREADY LOADED. CALCULATING DIFFERENCE!!!')
                        
                        # Update the existing data object with the new data
                        self._data[domain].updateData(dataobject)
                    else:
                        self._data[domain] = dataobject
                # Set the data object and return it
                else:
                    self._data[domain] = dataobject
                # Return the domain object
                return self._data[domain]
            else:
                raise Exception('Not a valid DataObject')
        except Exception as e:
            self.logger.warn(f'Failed to load data domain "{domain}" ({e})')
            return None
        
    def unloadDomain(self, domain, sync=False):
        '''
        Unloads the domain related DataObject from this store and returns it
        :param str domain: The data domain
        '''
        try:
            domain = domain.lower()
            self.logger.debug(f'Unloading data domain "{domain}" from {"persistent" if self.persistent else "ephemeral"} store "{self.name}"')
            dataobject = self._data[domain]
            if isinstance(dataobject, DataObject):
                # Sync data before unloading (Default false)
                if sync and dataobject.tainted:
                    self.syncDomain(domain)
                
                # Then unload domain
                self._unloadDomain(domain, self.path)
                
                # Close IO handle when still open
                if dataobject._iohandle is not None:
                    try:
                        dataobject._iohandle.close()
                    except:
                        dataobject._iohandle.stop()
                    finally:
                        del dataobject._iohandle
                        dataobject._iohandle = None
                
                # Remove domain from data
                del self._data[domain]
            else:
                self.logger.warn(f'Failed to unload data domain "{domain}" (Domain not loaded)')
        except KeyError:
            self.logger.warn(f'Failed to unload data domain "{domain}" (Domain was not loaded)')
        except Exception as e:
            self.logger.warn(f'Failed to unload data domain "{domain}" ({e})')
            
    def sync(self, force=False):
        '''
        Syncs all domain related DataObjects of this store if writable and persistent.
        A store can implement two different sync strategies influenced by the store variable
        "_sync_parallel". By default a store tries to sync all its domains at once, which makes sense
        if the backends are domain specific (For instance one file per domain). This parallelized 
        strategy makes lesser sense when we use for instance a database backend and therefore
        the sync strategy should be switched to a sequential approach by setting "_sync_parallel" to False.
        :param bool force: Sync all domains regardless if their data has changed or not
        '''
        # Check if we can sync to backend
        if self.persistent:
            self.logger.debug(f'Syncing persistent store "{self}"')
            
            # Get the domain data objects that require being synced
            if force:
                domains = self.getAllDomains()
            else:
                domains = self.getSyncDomains()
                
            if len(domains) == 0:
                return
               
            # Do a sequential sync (One domain by one)
            if not self._sync_parallel:
                for domain in domains:
                    self.syncDomain(domain, force)
            else:
                # Get event loop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Get or create a queue
                try:
                    queue = self.__syncDomains
                except AttributeError:
                    queue = self.__syncDomains = deque()
                    
                # Add each domain to the queue
                for domain in domains:
                    queue.append(domain)
                
                # Coroutine   
                async def syncWorker(queue, loop, executor):
                    while len(queue) != 0:
                        domain = queue.popleft()
                        await loop.run_in_executor(None, self.syncDomain, *[domain, force])
                
                # Create worker pool (Max number regulated by self._sync_max_threads)
                workers = []
                with ThreadPoolExecutor(max_workers=len(domains)) as executor:
                    for domain in domains:
                        if len(workers) <= self._sync_max_threads-1:
                            workers.append(asyncio.ensure_future(syncWorker(queue, loop, executor), loop=loop))
                    
                    # Run all workers asynchronously
                    if workers:
                        loop.run_until_complete(asyncio.wait(workers))
        else:
            # Reset the change logs of the ephemeral store's domains
            for domain in self.getSyncDomains():
                self._data[domain].clearTainted()
            self.logger.warn(f'Store "{self}" cannot be synced ("{self}" is not persistent)')
    
    def syncDomain(self, domain, force=False):
        '''
        Syncs the domain related DataObjects of this store. This will asynchronously sync
        all changes made to the DataObject to its backend. If a DataObject is already busy 
        syncing its data, this second sync attempt will wait asynchronously until the first
        synchronisation has finished. This function will call a private py:function::_syncDomain
        which by default writes each changed data token value by py:function::_setRaw to its backend.
        :param str domain: The data domain name (refering to a loaded DataObject)
        :param bool force: Sync the data domain in any case also when data has not changed
        '''
        # Check if we can sync to backend
        if self.persistent:
            # Prepare domain name
            domain = domain.lower() if isinstance(domain, str) else domain
            # Get the domain data object
            if domain in self._data:
                dataobject = self._data[domain]
                # Check if domain data was changed or if a sync is forced
                if dataobject.tainted is True or force is True:

#                     # Add domain to sync queue
#                     try:
#                         queue = dataobject.__syncTasks
#                     except AttributeError:
#                         queue = dataobject.__syncTasks = asyncio.Queue(loop = loop)
#                     queue.put_nowait(domain)

                    # TODO: Checken ob nicht gerade syncing=True ist und solange warten.
                    # TodO: Async IO implementieren
                    
                    try:
                        self.logger.debug(f'Syncing persistent data domain "{domain}" of "{self}"')
                        # We must set the syncing status
                        dataobject.syncing = True
                        self._syncDomain(dataobject, self.path)
                    except Exception as e:
                        self.logger.warn(f'Failed to sync data domain "{domain}" of "{self}" ({e})')
                    finally:
                        dataobject.syncing = False
        # Reset the change logs of the ephemeral store domains
        else:
            dataobject.clearTainted()
            self.logger.warn(f'Data domain "{domain}" cannot be synced ("{self}" is not persistent)')
            
    def getSyncDomains(self):
        '''
        Returns all domain DataObjects which are tainted and need to be synced
        :returns: The list of DataObjects keys with changed data
        :rtype: [str]
        '''
        return [domain for domain in self._data if self._data[domain].tainted]
    
    def getAllDomains(self):
        '''
        Returns all domain DataObjects of this store
        :returns: The list of all DataObjects keys
        :rtype: [str]
        '''
        return list(self._data.keys())
            
    def _loadDomain(self, domain, path):
        '''
        Abstract method to load the domain related data backend as a DataObject.
        :param str domain: The data domain
        :param str path: The file system location (folder)
        :returns: The domain DataObject
        :rtype: py:class::freedm.data.objects.DataObject
        '''
        raise NotImplementedError(f'Abstract method _loadDomain not implemented in class "{self.__class__.__module__}.{self.__class__.__name__}"')
        
    def _unloadDomain(self, domain, path):
        '''
        Abstract method to unload the domain related data backend.
        :param py:class::freedm.data.objects.DataObject domain: The data domain object
        :param str path: The file system location (folder)
        '''
        raise NotImplementedError(f'Abstract method _unloadDomain not implemented in class "{self.__class__.__module__}.{self.__class__.__name__}"')
        
    def _syncDomain(self, domain, path):
        '''
        A basic sync method using the store's :function:_setRaw: to write back changed data 
        token by token to its related backend. You might want to override this sync method 
        for your own implementation or implement a proper :function:_setRaw: function.
        :param py:class::freedm.data.objects.DataObject domain: The data domain object
        :param str path: The file system location (folder)
        '''
        # Get the tokens that have changed
        tainted = domain.getTainted(reset=True)
        
        # Sync token by token
        for token in tainted:
            try:
                # Set the raw value in the backend 
                self._setRaw(domain, token, domain.getValue(token))
            except:
                # If a token fails to be synced set it again as tainted
                domain.setTainted(token)
        
class DataObject(dict):
    '''
    A data object is a data container representing one thematic data domain. It represents
    a backend (file, database, etc.) and caches the data of its backend in it's internal structure, 
    and provides a getter/setter based interface to read and write values and provides.
    '''
    
    # A backend descriptor (e.g. path to a file)
    _backend = None
    
    # An IO handle (e.g. file/socket handle)
    _iohandle = None
    
    # A list of changed tokens
    _changed = None
    
    # A flag indicating that the object currently is being synced
    _syncing = False
    @property
    def syncing(self):
        return self._syncing
    @syncing.setter
    def syncing(self, mode):
        if isinstance(mode, bool): self._syncing = mode
    
    # Data state: Indicates if data has been changed (and needs to be synced to its backend)
    @property
    def tainted(self):
        return len(self._changed) > 0
    @tainted.setter
    def tainted(self, mode):
        raise AttributeError('Tainted mode cannot be set manually')
    
    # Init
    def __init__(self, backend=None, handle=None, *args, **kwargs):
        '''
        Inits this dictionary with nested data and sets a backend descriptor 
        and/or or a filesystem handle.
        '''
        # Set the data
        super().__init__(*args, **kwargs)
        
        # Set a new changed queue where we track changes made by setting values
        self._changed = deque()
        
        # Set backend IO handle
        if isinstance(backend, str):
            self._backend = backend
        if handle is not None:
            self._iohandle = handle
            
    def updateData(self, dataobject):
        '''
        Updates the data structure of this data object instance by the data structure of another data object
        without changing the instance id of this data object. Also the iohandle referring to open
        files or sockets will be properly treated to avoid multiple handles
        :param py:class::freedm.data.objects.DataObject dataobject: The object which data gets copied
        '''
        if isinstance(dataobject, self.__class__):
            # First reset the own data
            self.clear()
            # Then copy key by key from the new dataobject
            for k,v in dataobject.items():
                self.__setitem__(k,v)
            # Try closing/replacing iohandle
            if self._iohandle is not None and dataobject._iohandle is not None:
                try:
                    self._iohandle.close()
                except:
                    self._iohandle.stop()
                finally:
                    del self._iohandle
                    self._iohandle = dataobject._iohandle
            # Replicate tainted status
            if dataobject.tainted:
                self._changed = dataobject._changed
            else:
                self.clearTainted()
    
    def clearTainted(self):
        '''
        Clears all tokens marked as tainted from the change log.
        '''
        self._changed.clear()
    
    def setTainted(self, token):
        '''
        Set this token as tainted because its value changed. Will add the token to the 
        change log (only once, so only if not already set before).
        :param str token: The token whos value changed
        '''
        if token not in self._changed:
            self._changed.append(token)
    
    def getTainted(self, reset=False):
        '''
        Returns the list of all key tokens whose underlying data had been affected
        by changes. In the case of several tokens of same or different hierarchy, this function
        will return the token with the correct hierarchy level to address all changes at once
        and to avoid too many sync efforts against the related backend.
        For instance:
        - Changes to "laboratory.1" and "laboratory.2" will return both tokens
        - Changes to "laboratory" and "laboratory.2" will return just the token "laboratory"
        - Changes to "laboratory.[]" and "laboratory.2" will return just the token "laboratory"
        :param bool reset: If set to ``True``, then the change log will be reset (emptied) as well
        '''
        if reset is True:
            tokens = [self._changed.popleft() for _c in range(0, len(self._changed))]
        else:
            tokens = list(self._changed)
        
        if '' in tokens:
            return ['*']
        else:
            reduced = []
            tokens.sort()
            for i,v in enumerate(tokens):
                # Get token relations
                this = v
                prev = tokens[i-1] if i != 0 else None
                
                # Compare tokens with previous token and already listed tokens
                if prev is None:
                    reduced.append(this)
                else:
                    if prev in this:
                        pass
                    elif reduced[-1] in this:
                        pass
                    else:
                        reduced.append(this)   
            return reduced
                
    def getValue(self, token, data=None):
        '''
        Retrieves the value related to the provided key token from the nested data structure (dict) 
        of this data object. If a value can be found, it is returned, otherwise a LookupError is thrown.
        Key tokens are alphanumeric keys separated by dots ("."). Tokens also support numeric IDs to
        reference an item in collections (lists) or an ID referenced items being part of an object (dict).
                
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
         
        Wildcard support is achieved by the key "+". It retrieves a dictionary of all sub data-structures, regardless
        if it is a list or dictionary.
           
        "settings.+.ports" corresponds to an array with the ports of all sub-elements of settings
        following structure:
            {"settings": {"samba": {"port": 1}, "postfix": {"port": 995}, "ssh": {"port": 22}}}
            
        :param str token: The key token
        :param str data: The optional data object used as entry point (Default=self)
        :returns: The value
        '''
        # The uppermost level (root) of the nested data structure to start at
        if data is None:
            data = self
        
        # If we should return the whole data domain and no sub token data
        if token == '':
            return data
        
        # The individual key tokens
        keys = token.split('.')
        
        # Try to find the key tokens in the nested dict structure
        try:
            for index, key in enumerate(keys):
                
                # Handle special keys
                
                # Check if we need to look for an ID entry, specified by a numeric token key...
                if key.isdigit():
                    if isinstance(data, dict):
                        try:
                            # Try with integer keys
                            data = data[int(key)]
                        except:
                            # Try with string keys (JSON limitation)
                            data = data[key]
                    elif isinstance(data, list):
                        data = data[int(key)]
                    else:
                        data = data[key]
                        
                # Check if we need to find a collection of elements ...
                elif key == '[]':
                    # Transform a "numerical dictionary" in a list
                    if isinstance(data, dict) and len(data.keys()) > 0 and all(k.isdigit() for k in data.keys()):
                        data = [v for k,v in data.items()]
                    # List can stay a list
                    elif isinstance(data, list):
                        pass
                    else:
                        raise Exception('Key "[]" cannot be resolved as collection')
                
                # Retrieve data by wildcard '+'
                elif key == '+':
                    # Identify the previous key
                    key_prev = keys[index-1] if index-1 >= 0 else None
                    key_next = keys[index+1] if index+1 < len(keys) else None
                    # Transform a "numerical dictionary" into a list
                    if isinstance(data, dict):
                        data = [{k:v} if not k.isdigit() else v for k,v in data.items()]
                    # Handle lists
                    elif isinstance(data, list):
                        try:
                            if key_prev == '+' or key_prev == '[]':
                                items = []
                                for i in data:
                                    try:
                                        k2 = next(iter(i))
                                        path = '.'.join(keys[index+1:])
                                    except IndexError:
                                        path = ''
                                    items.append({k2: self.getValue(path, i[k2])})
                                data = items
                                break
                            elif key_next.isdigit():
                                items = []
                                for i in data:
                                    try:
                                        path = '.'.join(keys[index+1:])
                                    except IndexError:
                                        path = ''
                                    items.append(self.getValue(path, i))
                                data = items
                                break
                        except:
                            pass
                    # Other data types
                    else:
                        data = None

                # Handle normal keys (including search queries)
                    
                # Just try to return the next element by key
                else:
                    # ...when its a dictionary
                    if isinstance(data, dict):
                        data = data[key]
                    # ...or for each item in a list
                    elif isinstance(data, list):
                        i = []
                        for v in data:
                            try:
                                i.append(v[key])
                            except:
                                pass
                        if len(i) == 0:
                            raise Exception(f'Key "{key}" not set in any objects')
                        else:
                            data = i
                    else:
                        raise Exception(f'Key/value mismatch for "{key}"')
        except KeyError:
            raise LookupError(f'Key "{key}" of Token "{token}" not found')
        except IndexError:
            raise LookupError(f'Key "{key}" of Token "{token}" out if index')
        except Exception as e:
            raise LookupError(f'Token "{token}" lookup failed ({e})')
        
        # Return the data matching the token
        
#         from freedm.utils.formatters import printPrettyDict
#         print(printPrettyDict(data))
        
        return data
    
    def setValue(self, token, value):
        '''
        Sets a new value for the provided key token in the nested data structure (dict) 
        of this data object. Key tokens are alphanumeric keys separated by dots ("."). 
        Tokens also support numeric IDs to set data of collections (lists) or an object 
        of ID referenced items.
        
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
        :param value: The value
        :returns: ``True`` if the value could be set
        :rtype: bool
        '''
        # The uppermost level (root) of the nested data structure to start at
        data = self
        
        # The individual key tokens
        keys = token.split('.')
        
        # We reset and rebuild the token which then gets saved to the change log
        token = []
        
        # Try to find the key tokens in the nested dict structure or add them as new data
        try:
            for index, key in enumerate(keys):
                # Get index position
                index_next = index + 1
                index_prev = index - 1
                index_last = (len(keys) - index) == 1
                
                # Set the value for the last key or use new dict
                new_value = value if index_last else {}
                
                # Handle numeric keys
                if key.isdigit() or key == '[]':
                    # Save the value as part of a collection (list)
                    if isinstance(data, list):
                        if key == '[]':
                            # Update token
                            token.append(str(len(data)))
                            # Append value at next index
                            data.append(new_value)
                        else:
                            # Update token
                            token.append(key)
                            # Fill list with empty values if it is too short
                            key = int(key)
                            if len(data) <= key:
                                for empty in range(len(data), key + 1):
                                    data.append(None)
                            # Add the value at the correct index
                            if isinstance(data[key], list) and isinstance(new_value, dict):
                                pass
                            else:
                                data[key] = new_value
                    # Save the value as part of an object (dict)
                    elif isinstance(data, dict):
                        # Distinguish the next numeric key if we create a new item
                        if key == '[]':
                            try:
                                key = str(sorted(list(map(int, data.keys()))).pop() + 1)
                            except:
                                key = '0'
                        # Update token
                        token.append(key)
                        # Add the value with the correct index key
                        data.update({key: new_value})
                    # Save the value in a new dictionary
                    else:
                        # Update token
                        token.append('0' if key == '[]' else key)
                        # Update data
                        data = {'0' if key == '[]' else key: new_value}
                        
                # In case the token is an empty string and we should set the whole data domain
                elif index_last and key == '':
                    data.update(new_value)
                
                # Handle normals keys
                else:
                    # Update token
                    token.append(key)
                    # Update data
                    if index_last:
                        # When the current data node is a dictionary
                        if isinstance(data, dict):
                            if key not in data:
                                data.update({key: new_value})
                            else:
                                data[key] = new_value
                        # When the current data node is a list
                        elif isinstance(data, list):
                            data[-1].update({key: new_value})
                        break
                    else:
                        # Look ahead if the next key is a numeric identifier
                        if keys[index_next].isdigit() or keys[index_next] == '[]':
                            if data.get(key) is None:
                                data[key] = new_value
                            else:
                                pass
                        # Make sure we set a new empty object if next key isn't yet an object (not set or different existing value)
                        elif not isinstance(data.get(key), dict):
                            data[key] = new_value

                # Set cursor to current key
                if key not in ('[]', ''):
                    data = data[key]
        except Exception as e:
            raise e
        
        # Rebuild token
        token = '.'.join(token)
        
        # Sets the data object as tainted (by adding the key token to the change log).
        self.setTainted(token)
        
        # Return the result  
        return True
    
        
# class oldConfigurationObject(object):
#     
#     _backend = None
#     
#     __defaults = {}
#     
#     __configuration = {}
#     
#     _tainted = False
#     
#     # Init
#     def __init__(self, configuration = None, defaults = None):
#         
#         # Set any provided configuration values or default structures
#         if checker.isDict(configuration):
#             self.__configuration = configuration
#         if checker.isDict(defaults):
#             self.__defaults = defaults
#         else:
#             self.__defaults = dict(
#                                   daemon = dict(port = 5000, address = 'localhost', debug = False),
#                                   freedm = dict(network = 'free.dm')
#                                   )
#         
#     def set(self, tokenized_key, value):
#         '''
#         Sets a hierarchically tokenized configuration parameter. For instance "pool.server1.port"
#         '''
#         pass
#         
#     def get(self, tokenized_key):
#         '''
#         Returns a hierarchically tokenized configuration parameter. For instance "pool.server1.port"
#         '''
#          
#         # Split the configuration into its tokens, then check for the value of the  attribute
#         keys = tokenized_key.split('.')
#         steps = 0
# 
#         # First: Search for the value in the configuration object
#         cursor = self.__configuration
#         for k in keys:
#             steps += 1
#             # Check if we access a list
#             if k.endswith(']'):
#                 k = k.split('[')[0]
#                 i = int(k.split('[')[1][0:-1])
#             # Check if key exists
#             if k in cursor:
#                 cursor = cursor[k]
#                 if checker.isList(cursor) and checker.isInteger(i):
#                     cursor = cursor[i]
#                     i = None
#                 if not checker.isIterable(cursor) or checker.isString(cursor):
#                     # Return here with "None" if we have lesser tokens than in the query
#                     if(steps > 0 and steps < len(keys)):
#                         # Return "None" here without a second check for default values
#                         return None
#                     elif(steps > 0 and steps == len(keys)):
#                         # Return the value without a second check for default values
#                         return cursor
#             else:
#                 cursor = None;
#                 break
#         
#         # Second: Search for the value in the default structure
#         if cursor == None:
#             cursor = self.__defaults
#             for k in keys:
#                 # Check if we access a list
#                 if k.endswith(']'):
#                     k = k.split('[')[0]
#                     i = int(k.split('[')[1][0:-1])
#                 # Check if key exists
#                 if k in cursor:
#                     cursor = cursor[k]
#                     if checker.isList(cursor) and checker.isInteger(i):
#                         cursor = cursor[i]
#                         i = None
#                     if not checker.isIterable(cursor):
#                         break
#                 else:
#                     cursor = None
#                     break
# 
#         # Return the value
#         return cursor