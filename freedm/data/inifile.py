'''
This module provides a DataStore based on INI-files
@author: Thomas Wanderer
'''

# Imports
import os
import json
from configparser import SafeConfigParser

# free.dm Imports
from freedm.data.store import DataStore
from freedm.data.object import DataObject
from freedm.utils.filesystem import FilesystemObserver
from freedm.utils.types import TypeChecker as checker
from freedm.utils.async import runConcurrently


class IniFileStore(DataStore):
    '''
    A data store which reads and writes its data from and to INI files. Due to the nature of 
    INI files, a token gets dissected into "domain" (referring to the INI file), a
    "category" (referring to an INI section) and a "key" (referring to a key/value pair).
    Any longer token is mapped to a value representing a JSON encoded data structure in the file.
    While JSON encoded values allow for longer tokens, this is not optimal and loses the advantage 
    of INI files which is easy readability.
    This class supports a default dynamic reading/writing of INI files or keeping the datastore with its
    file backend in sync at all time making manual syncs unnecessary.
    '''
    # Attributes 
    _persistent = True
    _writable = True
    _default_name = 'Config'
    _default_filetype = 'ini'
    description = 'A persistent INI file store'
                
    @DataStore.path.setter
    def path(self, path):
        # First, set the path
        DataStore.path.__set__(self, path)
        
        # In synced mode read all data and observe changes
        if self.synced and path is not None and self._iohandle is None:
            # Start observing the path
            self.__observeFiles()
            # Then load all file backends
            self.__loadFiles()
            
    # Private method to load all backend files
    def __loadFiles(self):
        # Gather INI files to load
        files = []
        for file in os.listdir(self.path):
            if file.endswith(f'.{self.filetype}'):
                files.append(str(os.path.splitext(file)[0]))
        
        # Load INI files concurrently
        runConcurrently(self.loadDomain, files)
        
    # Private method to setup path observer
    def __observeFiles(self):
        try:
            # Create a subclass implementing the FilesystemObserver's abstract event methods
            class Observer(FilesystemObserver):
                def onFileModified(self, event, store=self):
                    # Update domain data object
                    store.loadDomain(str(os.path.splitext(os.path.basename(event.src_path))[0]))
                    print('STORE DATA =', store._data)
                    
                def onFileCreated(self, event, store=self):
                    # As "onFileModified" is fired thereafter we do nothing here
                    pass
                    
                def onFileDeleted(self, event, store=self):
                    # Unload domain data object
                    store.unloadDomain(str(os.path.splitext(os.path.basename(event.src_path))[0]))
                    print('STORE DATA =', store._data)
                    
                def onFileMoved(self, event, store=self):
                    # Get domain names from files
                    src, src_type = os.path.splitext(os.path.basename(event.src_path))
                    dest, dest_type = os.path.splitext(os.path.basename(event.dest_path))
                    
                    # Unload old domain data object
                    if src_type.endswith(store.filetype) and src != dest:
                        store.unloadDomain(str(src))
                    # Load new ddomain data object
                    if dest_type.endswith(store.filetype):
                        store.loadDomain(str(dest))
                    print('STORE DATA =', store._data)
            
            # Set the observer as handle and start
            if self._iohandle is None and self.path is not None:
                self._iohandle = Observer(self.path, filetypes=self.filetype)
                self._iohandle.start()
                self.logger.debug(f'Data store "{self}" now observes path "{self.path}" (Files: "*.{self.filetype}")')
        except Exception as e:
            self.logger.warn(f'Cannot observe path ({e})')
            
    # Release the directory observer
    def releaseHandle(self):
        if self._iohandle is not None:
            try:
                self._iohandle.stop()
                self._iohandle = None
                self.logger.debug(f'Data store "{self}" stopped observing path "{self.path}" (Files: "*.{self.filetype}")')
            except Exception as e:
                self.logger.warn(f'Failed to stop filesystem observer for path ({e})')
                raise e
            
    # Implement data setters & getter
    def _setRaw(self, domain, token, value):
        # TODO: Implement sill
#         if self.synced and self._iohandle:
#             with self._iohandle._watchdog.interruptObserver():
#                 with open(os.path.join(self.path, domain), 'w') as f:
                    pass
                    #f.write('TODO: INIFILE DATA')
    
    def _getRaw(self, domain, token):
        print('## GETTNG R-A-W !!!', token)
    
    # Implement domain loading and unloading
    def _loadDomain(self, domain, path):
        try:
            assert path != None, 'No file location provided'
            # The backend file
            inifile = path.joinpath(f'{domain}.{self.filetype}')
            
            # Read the data from file & convert values
            parser = SafeConfigParser()
            parser.read(inifile)
            inidata = {}
            for s in parser.sections():
                items = []
                # Handle each item
                for item in parser.items(s):
                    # Try to convert item values automatically
                    try:
                        k, v = item
                        if v is not None:
                            # Get integers from config file
                            if v.isdigit():
                                v = parser.getint(s, k)
                            # Get floats from config file
                            elif checker.isFloat(v):
                                v = parser.getfloat(s, k)
                            # Get booleans from config file
                            elif v in ('1', 'yes', 'true', 'on', '0', 'no', 'false', 'off'):
                                v = parser.getboolean(s, k)
                            # Get nested JSON objects from config file
                            elif v.startswith('{') and v.endswith('}'):
                                v = json.loads(v)
                            # Get nested JSON objects from config file
                            elif v.startswith('[') and v.endswith(']'):
                                v = json.loads(v)
                            # Get wrapped values as string
                            elif v[0] in ('"', '\'') and v[-1] in ('"', "'"):
                                v = v[1:-1]
                        items.append((k, v))  
                    except Exception as e:
                        print(e.__class__.__name__)
                        if e.__class__.__name__ in ('json.JSONDecodeError', 'ValueError'):
                            raise UserWarning(f'File "{inifile}" cannot be JSON-decoded ({e})!')
                        else:
                            items.append(item)
                # Re-add all items & sections 
                inidata.update({s:dict(items)})
            
            # Create data object
            if isinstance(inidata, dict):
                data = DataObject(backend=inifile, **inidata)
                return data
        except FileNotFoundError:
            raise UserWarning(f'File "{inifile}" does not exist. Please create this file!')
        except Exception as e:
            raise e
        
    def _unloadDomain(self, domain, path):
        pass
    
    def _syncDomain(self, domain, path):
        print('TODO: Implement or get rid of this _syncDomain method')