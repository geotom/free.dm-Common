'''
This module defines a generic data object
@author: Thomas Wanderer
'''

# Imports
from collections import deque
from typing import ItemsView, Optional, Union, List, Dict, Any, Type


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
                                for _ in range(len(data), key + 1):
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