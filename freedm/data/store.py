'''
This module defines a generic data store
@author: Thomas Wanderer
'''

# Imports
import os
import logging
import asyncio
import uvloop
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Union, Tuple, List, Dict, Any, Type
from logging import Logger

# free.dm Imports
from freedm import models
from freedm.data.object import DataObject
from freedm.utils.aio import runConcurrently


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
    _default_name: str = 'data'
    _default_filetype: str = 'cfg'
    
    # Sync strategy
    _sync_parallel: bool = True       # Data domains should be simultaneously synced => True or sequentially => False
    _sync_max_threads: int = 10      # The max number of parallel sync operations/threads if parallel sync is enabled
    
    @property
    def path(self) -> Optional[Path]:
        '''The filesystem storage location represented by this class instance'''
        try:
            return self.__path
        except AttributeError:
            return None
    @path.setter
    def path(self, path: Union[str, Path]):
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
    def filetype(self) -> str:
        '''The filetype (suffix .*) used by this store's filesystem based backends'''
        try:
            return self.__filetype
        except AttributeError:
            return self._default_filetype
    @filetype.setter
    def filetype(self, extension: str):
        if isinstance(extension, str):
            self.__filetype = extension[1:] if extension.startswith('.') else extension
            
    @property
    def alias(self) -> str:
        '''The optional alias of the data store. By default the alias is build from the store's name'''
        try:
            return self.__alias if self.__alias is not None else self.name.lower().capitalize()
        except AttributeError:
            return self.name.lower().capitalize()
    @alias.setter
    def alias(self, name: str):
        if isinstance(name, str) and name.isalpha():
            self.__alias = name.lower().capitalize()
        else:
            raise AttributeError(f'Invalid freedm.data.objects.DataStore alias "{name}". Must be an alphabetical string')
        
    @property
    def name(self) -> str:
        '''The store's name. Used to derive the alias of the store if not set separately'''
        try:
            return self.__name if self.__name is not None else self._default_name
        except AttributeError:
            return self._default_name
    @name.setter
    def name(self, name: str):
        if isinstance(name, str) and name.isalpha():
            self.__name = name
        else:
            raise AttributeError(f'Invalid freedm.data.objects.DataStore name "{name}". Must be an alphabetical string')
    
    # Data persistence: Indicates that data of this store is read from/written to a filesystem or database backend
    _persistent = False
    @property
    def persistent(self) -> bool:
        return self._persistent
    @persistent.setter
    def persistent(self, mode: bool):
        raise AttributeError('Set this attribute on instancing the store')
    
    # Data write mode: indicates that we can set/unset values. If a store is persistent, it means the store also must be writable
    _writable = True
    @property
    def writable(self) -> bool:
        return True if self.persistent else self._writable
    @writable.setter
    def writable(self, mode: bool):
        raise AttributeError('Set this attribute on instancing the store')
    
    # Sync mode: Indicates that all data changes are immediately synchronized between backend and dataobject
    _synced = True
    @property
    def synced(self) -> bool:
        return self._synced
    @synced.setter
    def synced(self, mode: bool):
        raise AttributeError('Set this attribute on instancing the store')
    
    @property
    def logger(self) -> Type[Logger]:
        '''The logger of this class'''
        return logging.getLogger(str(os.getpid()))
        
    # Store description
    description: str = None
        
    # DataObject store
    _data: Dict[str, Any] = {}
    
    # An optional IO handle for stores with filesystem backends or persistent socket connections
    _iohandle: Dict[str, Any] = None
    
    # Representation
    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.alias}>'
    
    # Init
    def __init__(self, name: str=None, alias: str=None, description: str=None, path: Union[str, Path]=None, filetype: str=None, writable: bool=None, persistent: bool=None, synced: bool=False):
        '''
        :param str name: An alphabetical name without whitespace characters (Used for setters/getters) 
        :param str alias: An optional alphabetical alias without whitespace characters (Used instead of the name for setters/getters) 
        :param str description: The store description
        :param str path: An optional file system location (folder). Will otherwise be set by the data manager
        :param str filetype: An optional file suffix (.*) for file backends used by this store
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
    def __tokenize(self, token: str) -> Tuple[Type[DataObject], str]:
        '''
        This method dissects a key token into its components representing the domain part and the data key.
        It maps the domain token to a loaded/auto-loaded DataObject (domain) if possible. If not, the returned
        domain will be just a string.
        :param str token: The token
        :returns: The name (string or data object) representing the domain and the tokenized keys
        :rtype: [str/py:class::freedm.data.objects.DataObject]
        '''
        # Return objects
        domain: Type[DataObject] = None
        tokens: str = None
         
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
    def releaseHandle(self) -> None:
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
        runConcurrently(domainReleaser, [domain for _, domain in self._data.items()])

    # Value getting and setting
    def setValue(self, token: str, value: Any) -> bool:
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
        
    def getValue(self, token: str, default: Any=None) -> Any:
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
        value: Any = None
        
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
    
    def _setRaw(self, domain: Type[DataObject], token: str, value: Any) -> None:
        '''
        Abstract method to store the raw value into a data objects.
        :param py:class::freedm.data.objects.DataObject domain: The domain data object
        :param str token: The key token
        :param object value: The value
        :returns: ``True`` if the value could be set
        :rtype: bool
        '''
        raise NotImplementedError(f'Abstract method _setRaw not implemented in class "{self.__class__.__module__}.{self.__class__.__name__}"')
            
    def _getRaw(self, domain: Type[DataObject], token: str) -> Any:
        '''
        Abstract method to retrieve the raw value from a DataObject.
        :param py:class::freedm.data.objects.DataObject domain: The domain data object
        :param str token: The key token
        :returns: The value
        '''
        raise NotImplementedError(f'Abstract method _getRaw not implemented in class "{self.__class__.__module__}.{self.__class__.__name__}"')
            
    # Data backend loading        
    def getDomain(self, domain: str) -> Optional[Type[DataObject]]:
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
            
    def loadDomain(self, domain: str) -> Optional[Type[DataObject]]:
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
        
    def unloadDomain(self, domain: str, sync: bool=False) -> None:
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
            
    def sync(self, force: bool=False) -> None:
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
                    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
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
                            workers.append(asyncio.create_task(syncWorker(queue, loop, executor)))
                    
                    # Run all workers asynchronously
                    if workers:
                        loop.run_until_complete(asyncio.wait(workers))
        else:
            # Reset the change logs of the ephemeral store's domains
            for domain in self.getSyncDomains():
                self._data[domain].clearTainted()
            self.logger.warn(f'Store "{self}" cannot be synced ("{self}" is not persistent)')
    
    def syncDomain(self, domain: str, force: bool=False) -> None:
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
            
    def getSyncDomains(self) -> List[DataObject]:
        '''
        Returns all domain DataObjects which are tainted and need to be synced
        :returns: The list of DataObjects keys with changed data
        :rtype: [List]
        '''
        return [domain for domain in self._data if self._data[domain].tainted]
    
    def getAllDomains(self) -> List[str]:
        '''
        Returns all domain DataObjects of this store
        :returns: The list of all DataObjects keys
        :rtype: [str]
        '''
        return list(self._data.keys())
            
    def _loadDomain(self, domain: str, path: str) -> None:
        '''
        Abstract method to load the domain related data backend as a DataObject.
        :param str domain: The data domain
        :param str path: The file system location (folder)
        :returns: The domain DataObject
        :rtype: py:class::freedm.data.objects.DataObject
        '''
        raise NotImplementedError(f'Abstract method _loadDomain not implemented in class "{self.__class__.__module__}.{self.__class__.__name__}"')
        
    def _unloadDomain(self, domain: str, path: str) -> None:
        '''
        Abstract method to unload the domain related data backend.
        :param py:class::freedm.data.objects.DataObject domain: The data domain object
        :param str path: The file system location (folder)
        '''
        raise NotImplementedError(f'Abstract method _unloadDomain not implemented in class "{self.__class__.__module__}.{self.__class__.__name__}"')
        
    def _syncDomain(self, domain: Type[DataObject], path: str) -> None:
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