'''
This module provides a DataStore based on a SQL database
@author: Thomas Wanderer
'''

# free.dm Imports
from freedm.data.store import DataStore
from freedm.data.object import DataObject


class SQLStore(DataStore):
    '''
    A data store which reads and writes its data from and to a SQL Database.
    This store translates tokens into tables and rows. Data tokens therefore must be
    of a minimal length of one token and will be dissected into "db_table" and "db_table_column".
    Any further subtokens will lead to a try to deserialize the found column data as JSON and 
    look up the token within this data structure.
    
    Examples:
    - store.getValue('users') will return all user objects in the db_table "users"
    - store.getValue('users.name') will return all user names from the db_table "users" column "name"
    - store.getValue('users.settings.key') will try to deserialize the data as JSON from the db_table "users" column "data" and return the element "key"
    - store.getValue('users.45') will return the user's data with id=45 from the db_table "users"
    - store.getValue('users.45.name') will return the name of the user with id=45 from the db_table "users" column "name"
    
    This store supports the synced mode to autoload a DB table's data and to be 
    notified when changes are written to the database.
    '''
    # Attributes
    _persistent = True
    _writable = True
    _default_name = 'pgSQL'
    description = 'A persistent PostgreSQL database store'
    
    # Set up a file monitoring observer
    def __init__(self, *args, address=None, port=None, user=None, password=None, **kwargs):
        '''
        Creates a new instance of a INI file based data store. This class supports
        a default dynamic reading/writing of INI files or keeping the datastore with its
        file backend in sync at all time making manual syncs unnecessary.
        :param address str: The address of the database
        :param port int: The port of the database
        :param user str: The database user's name
        :param password str: The database user's password
        ''' 
        # Init the store
        super().__init__(*args, **kwargs)
        
        # Unset path information
        self.path = False
        
        # Create database connection
        if self.synced:
            self.__connect()
            
    def __connect(self):
        '''
        Opens the database and sets the fshandle
        '''
        pass
        #self.fshandle = 