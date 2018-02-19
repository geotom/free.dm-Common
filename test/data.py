'''
This test checks the functionality of the free.dm data module
@author: Thomas Wanderer
'''

# Imports
import unittest
import os
import sys
import shutil
import string
import random
import logging
import json
from threading import Thread

# Test imports
import __init__

# free.dm Imports
import freedm.data as data
import freedm.models as models


# Setup schema and data for testing
models.person = {
                   'type': 'object',
                   'properties': {
                                  'maidenname': {
                                                 'type': 'string',
                                                 'default': 'Mädchenname'
                                                },
                                  'gender': {
                                             'type': 'string',
                                             'enum': ['male', 'female'],
                                             'default': 'female'
                                            }
                                  }
                   }

models.integer = {
                    'type': 'integer',
                    'default': 0
                    }

models.user = {
                 'type': 'object',
                 'required': ['active', 'blocked'],
                 'additionalProperties': False,
                 'properties': {
                                'active': {
                                           'type': 'array',
                                           'items': {
                                                     'type': 'object',
                                                     'required': ['name', 'surname'],
                                                     'additionalProperties': False,
                                                     'properties': {
                                                                    'name': {'type': 'string', 'description': 'A user name', 'default': 'Vorname'},
                                                                    'surname': {'type': 'string', 'description': 'A user surname', 'default': 'Nachname'}
                                                                    }
                                                            }
                                                    },
                                'blocked': {
                                            'type': 'array',
                                            'items': {
                                                      'type': 'object',
                                                      'required': ['name', 'surname'],
                                                      'additionalProperties': False,
                                                      'properties': {
                                                                     'name': {'type': 'string', 'description': 'A user name', 'default': 'Vorname'},
                                                                     'surname': {'type': 'string', 'description': 'A user surname', 'default': 'Nachname'}
                                                                    }
                                                     }
                                            },
                                'new': {
                                           'type': 'array',
                                           'items': {
                                                     'type': 'object',
                                                     'required': ['name', 'surname'],
                                                     'additionalProperties': True,
                                                     'properties': {
                                                                    'name': {'type': 'string', 'description': 'A user name', 'default': 'Vorname'},
                                                                    'surname': {'type': 'string', 'description': 'A user surname', 'default': 'Nachname'}
                                                                   }
                                                    }
                                          }
                               }
                 }

models.dummy = {
                'type': 'object',
                'properties': {
                               'test2': {
                                         'type': 'array',
                                         'items': {
                                                   'type': 'object',
                                                   'required': ['role'],
                                                   'additionalProperties': False,
                                                   'properties': {
                                                                  'role': {
                                                                              'type': 'object',
                                                                              'required': ['name', 'lastname'],
                                                                              'additionalProperties': False,
                                                                              'properties': {
                                                                                             'name': {
                                                                                                      'type': 'string',
                                                                                                      'description': 'A Star Wars charcter name',
                                                                                                      'enum': ['Luke', 'Han', 'Darth'],
                                                                                                      'default': 'Luke'
                                                                                                      },
                                                                                             'lastname': {
                                                                                                          'type': 'string',
                                                                                                          'description': 'A Star Wars charcter last name',
                                                                                                          'enum': ['Skywalker', 'Vader', 'Solo'],
                                                                                                          'default': 'Skywalker'
                                                                                                          },
                                                                                             'age': {
                                                                                                     'type': 'integer',
                                                                                                     'description': 'A Star Wars charcter\'s age',
                                                                                                     }
                                                                                             }
                                                                           }
                                                                  }
                                                   }
                                         }
                              } 
                }


# Setup logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler(sys.stdout))

# Utility functions
def getRandomString():
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

# Test the memory store
class MemoryStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logger.info('Starting unittest: {}'.format(cls.__name__))
        cls.store = data.MemoryStore()
    
    @classmethod   
    def tearDownClass(cls):
        logger.info('Ending unittest: {}'.format(cls.__name__))
        cls.store = None
    
    def testStoreConfig(self):
        self.assertEqual(self.store.alias, 'Cache', 'Store alias is not "Cache"')
        self.assertEqual(self.store.name, 'Cache', 'Store name is not "Cache"')
        self.assertEqual(self.store.path, False, 'Store path is not "False"')
        self.assertEqual(self.store.filetype, '', 'Store filetype is not ""')
        self.assertEqual(self.store.persistent, False, 'Store must not be persistent')
        self.assertEqual(self.store.writable, True, 'Store must be writable')
        self.assertEqual(self.store.synced, False, 'Store must not be synced')
        self.assertEqual(self.store._iohandle, None, 'Store should have no iohandle')
       
    def testDefaultValues(self):
        tests = {
                 # TOKEN, DEFAULT VALUE
                 'notset': None,
                 'user': {'active': [], 'blocked': []},
                 'user.active': [],
                 'user.active.5': {'surname': 'Nachname', 'name': 'Vorname'},
                 'user.active.5.name': 'Vorname',
                 'user.active.[]': [],
                 'user.active.[].name': [],
                 'user.active.name': 'Vorname',
                 'user.active.surname': 'Nachname',
                 'user.active.notset': None,
                 'person': {'maidenname': 'Mädchenname', 'gender': 'female'},
                 'person.maidenname': 'Mädchenname',
                 'daemon': {'rpc': {'port': 5000, 'address': 'localhost'}},
                 'daemon.rpc': {'port': 5000, 'address': 'localhost'},
                 'daemon.rpc.address': 'localhost',
                 'daemon.rpc.port': 5000,
                 'integer': 0,
                 'dummy.test2': [],
                 'dummy.test2.role': {'name': 'Luke', 'lastname': 'Skywalker'},
                 'dummy.test2.role.name': 'Luke'
                 }
        for token, default in tests.items():
            try:
                logger.debug('Getting default value for token "{}"'.format(token))
                # Get default
                result = models.getDefaultValue(token)
                # Compare with predefined default
                if isinstance(result, dict):
                    self.assertDictEqual(result, default, 'Default value token "{}" false ({})'.format(token, result))
                elif isinstance(result, list):
                    self.assertListEqual(result, default, 'Default value token "{}" false ({})'.format(token, result))
                else:
                    self.assertEqual(result, default, 'Default value token "{}" false ({})'.format(token, result))
            except Exception as e:
                logger.critical('Failed to get correct value for token "{}" ({} != {})'.format(token, result, default))
                raise e
            
    def testValidateValues(self):
        tests = [
                 # TOKEN, (VALUE, NEGATIVE RESULT)
                 ('integer', (8,)),
                 ('integer', (1.0, None)),
                 ('integer', (0.0, None)),
                 ('person', ({'maidenname': 'Simpson', 'gender': 'unknown'}, None)),
                 ('person.gender', ('unknown', None)),
                 ('person.gender', ('male',)),
                 ('user.active', ([{'surname': 'Simpson', 'name': 'Homer'}, {'surname': 'Flanders', 'name': 'Ned'}, {'surname': 'Burns', 'name': 'Monty'}],)),
                 ('user.active', ([{'surname': 'Burns', 'name': 12}], None)),
                 ('user.active', ({'surname': 'Burns', 'name': 12}, None)),
                 ('user.active.5', ([{'surname': 'Simpson', 'name': 'Bart'}],)),
                 ('user.active.[]', ({'surname': 'Simpson', 'name': 'Bart'}, None)),
                 ('user.active.[]', ([{'surname': 'Simpson', 'name': 'Bart'}],)),
                 ('user.active.3.name', ('Bart',)),
                 ('user.active.3.name', ([], None)),
                 ('user', ({'active': [], 'blocked': []},)),
                 ('user', ({'active': [], 'new': {}}, None)),
                 ('user', ({'active': []}, None)),
                 ('user', ({'active': [], 'blocked': [], 'inactive': []}, None)),
                 ('daemon', ({'rpc': {'port': 5000, 'address': 'server.org'}},)),
                 ('daemon', ({'rpc': {'port': 1000, 'address': 'server.org'}}, None)),
                 ('daemon', ({'rpc': {'port': 5000}}, None)),
                 ('daemon.rpc.port', (5000,)),
                ]
        
        # Test the returned values 
        for token, values in tests:
            try:
                logger.debug('Get validated value for token "{}" with value "{}"'.format(token, values[0]))
                # Define value to check against
                if len(values) == 1:
                    check = values[0]
                else:
                    check = values[1]
                # Get validation result
                result = models.getValidatedValue(token, values[0])
                # Compare with predefined default
                if isinstance(check, dict):
                    self.assertDictEqual(result, check, 'Validated value of token "{}" is of wrong value ({})'.format(token, result))
                elif isinstance(check, list):
                    self.assertListEqual(result, check, 'Validated value of token "{}" is of wrong value ({})'.format(token, result))
                else:
                    self.assertEqual(result, check, 'Validated value of token "{}" is of wrong value ({})'.format(token, result))
            except Exception as e:
                logger.critical('Failed to get valid value for token "{}" ({} != {})'.format(token, result, check))
                raise e
        
        # Test the validation itself   
        for token, values in tests:
            try:
                logger.debug('Validating token "{}" with value "{}"'.format(token, values[0]))
                # Define value to check against
                if len(values) == 1:
                    check = values[0]
                else:
                    check = values[1]
                # Get validation result
                result, value = models.isValidValue(token, values[0])
                
                # Compare with predefined default
                if check is None:
                    self.assertFalse(result, 'Validation of token "{}" failed'.format(token))
                else:
                    self.assertTrue(result, 'Validation of token "{}" failed'.format(token))
            except Exception as e:
                logger.critical('Failed to validate token "{}" ({} != {})'.format(token, result, check))
                raise e
            
    def testSetValues(self):
        tests = [
                 # TOKEN, VALUE, EXPECTED RESULT
                 ('random.model.name', 'Homer', True),
                 ('random.model.name', 'Bart', True),
                 ('random.model.name', 'Moe', True),
                 ('person', 'Moe', False),
                 ('person', None, False),
                 ('person', [], False),
                 ('person', 1, False),
                 ('person', {}, True),
                 ('person', {'maidenname': 'Bouvier'}, True),
                 ('person', {'gender': 'Simpson'}, False),
                 ('person', {'haircolor': 'blue'}, True),
                 ('user', {}, False),
                 ('daemon.rpc.port', '6000', False),
                 ('daemon.rpc.port', 6000, True),
                 ('daemon.rpc.address', 'www.website.com', True),
                 ('daemon.rpc.port.ipv4', 125, False),
                 ('dummy.test1', {}, True),
                 ('dummy.test1.4.details', {'name': 'Maggie'}, True),
                 ('dummy.test1.[].details', {'name': 'Lisa'}, True),
                 ('dummy.test1.9.details', {'name': 'Bart'}, True),
                 ('dummy.test3.neu', 'A String', True),
                 ('dummy.test3', 'Overwritten', True),
                 ('dummy.test4.range', [], True),
                 ('dummy.test4.range.0', 'First', True),
                 ('dummy.test4.range.9', 'Last', True),
                 ('dummy.test4.range.[]', 'Really the last', True),
                 ('dummy.test5.struct.struct.struct.struct', [], True),
                 ('dummy.test6', [], True),
                 ('dummy.test6.[].word', 'Hallo', True),
                 ('dummy.test6.0.[]', 'Servus', True),
                 ('dummy.test7.4', 'Hallo', True),
                 ('dummy.test8', [], True),
                 ('dummy.test8.[]', [], True),
                 ('dummy.test8.[]', [], True),
                 ('dummy.test8.0.1', 'One', True),
                 ('dummy.test8.1.[]', 'Zero', True),
                 ('daemon', {'rpc': {'address':'host.internet', 'port': 5555}}, True),
                 ('dummy.test2', [], True),
                 ('dummy.test2.[].role', {'name': 'Luke', 'lastname': 'Skywalker', 'age': 30}, True),
                 ('dummy.test2.[].role', {'name': 'Darth', 'lastname': 'Vader', 'age': 60}, True),
                 ('dummy.test2.[].role', {'name': 'Han', 'lastname': 'Solo', 'age': 40}, True),
                 ('dummy.test9', [], True),
                 ('dummy.test9.[]', [1,2,3], True),
                 ('dummy.test9.[]', ['A', 'B', 'C'], True)
                 ]
        
        # Do not set the data more than once
        if len(self.store.getSyncDomains()) == 0:
            # Test if values were set
            for token, value, result in tests:
                try:
                    if result:
                        self.assertTrue(self.store.setValue(token, value), 'Cannot set value "{}" with token "{}"'.format(value, token))
                    else:
                        self.assertFalse(self.store.setValue(token, value), 'Setting value "{}" with token "{}" should have failed'.format(value, token))
                except Exception as e:
                    logger.critical('Failure when setting value "{}" as token "{}" ({})'.format(value, token, e))
                    raise e
        
        # Test the proper reduction of changes in the change log that would be used for syncing
        checks = {
                  'dummy': (27, 9),
                  'daemon': (3, 1),
                  'random': (1, 1),
                  'person': (1, 1)
                  }
        for d in self.store._data:
            changed = list(self.store._data[d]._changed)
            reduced = self.store._data[d].getTainted()
            self.assertEqual(len(changed), checks[d][0], 'The change log for domain "{}" is of incorrect length'.format(d))
            self.assertEqual(len(reduced), checks[d][1], 'The reduced change log for domain "{}" is of incorrect length'.format(d))
            
        # Test the data state after setting new values
        try:
            self.assertTrue(self.store._data['daemon']['rpc']['port'] == tests[36][1]['rpc']['port'], 'Daemon RPC port is not "{}"'.format(tests[36][1]['rpc']['port']))
            self.assertTrue(isinstance(self.store._data['dummy']['test1'], object), 'Test1 is not an object')
            self.assertTrue(self.store._data['dummy']['test1']['4']['details'] == tests[17][1], 'Details for Maggie are not "{}"'.format(tests[17][1]))
            self.assertTrue(len(set(self.store._data['dummy']['test1'].keys()).difference(['4', '5', '9'])) == 0, 'Test 1 has not the correct keys')
            self.assertTrue(self.store._data['dummy']['test3'] == tests[21][1], 'Test 3 is not "{}"'.format(tests[21][1]))
            self.assertTrue(len(self.store._data['dummy']['test4']['range']) == 11, 'Test 4 does not return the correct element count')
            self.assertTrue(self.store._data['dummy']['test4']['range'][0] == tests[23][1], 'Elements in Test 4 do not have the right value "{}"'.format(tests[23][1]))
            self.assertTrue(self.store._data['dummy']['test4']['range'][1] == None, 'Elements in Test 4 do not have the right value "{}"'.format(None))
            self.assertTrue(self.store._data['dummy']['test4']['range'][8] == None, 'Elements in Test 4 do not have the right value "{}"'.format(None))
            self.assertTrue(self.store._data['dummy']['test4']['range'][9] == tests[24][1], 'Elements in Test 4 do not have the right value "{}"'.format(tests[24][1]))
            self.assertTrue(self.store._data['dummy']['test4']['range'][10] == tests[25][1], 'Elements in Test 4 do not have the right value "{}"'.format(tests[24][1]))
            self.assertTrue(isinstance(self.store._data['dummy']['test5']['struct']['struct']['struct']['struct'], list), 'Elements in Test 5 do not have the right value "{}"'.format(tests[25][1]))
            self.assertTrue(self.store._data['dummy']['test6'][0]['0'] == tests[29][1], 'Elements in Test 6 do not have the right value "{}"'.format(tests[29][1]))
            self.assertTrue(self.store._data['dummy']['test7']['4'] == tests[30][1], 'Elements in Test 7 do not have the right value "{}"'.format(tests[30][1]))
            self.assertTrue(len(self.store._data['dummy']['test8']) == 2, 'Test 8 does not return the correct element count')
            self.assertTrue(len(self.store._data['dummy']['test8'][0]) == 2, 'Test 8 does not return the correct element count')
            self.assertTrue(len(self.store._data['dummy']['test8'][1]) == 1, 'Test 8 does not return the correct element count')
            self.assertTrue(self.store._data['dummy']['test8'][0][1] == tests[34][1], 'Elements in Test 8 do not have the right value "{}"'.format(tests[34][1]))
            self.assertTrue(self.store._data['dummy']['test8'][1][0] == tests[35][1], 'Elements in Test 8 do not have the right value "{}"'.format(tests[35][1]))
            self.assertTrue(self.store._data['person']['haircolor'] == tests[10][1]['haircolor'], 'Person attribute does not have the right value "{}"'.format(tests[10][1]['haircolor']))
            self.assertTrue(self.store._data['person']['maidenname'] == tests[8][1]['maidenname'], 'Person attribute does not have the right value "{}"'.format(tests[8][1]['maidenname']))
            self.assertTrue(len(self.store._data['person'].keys()) == 2, 'Person does not return the correct attribute count')
            self.assertTrue(self.store._data['random']['model']['name'] == tests[2][1], 'Random model name is not "{}"'.format(tests[2][1]))
        except Exception as e:
            logger.critical('Failure when checking set values ({})'.format(e))
            raise e
        
        # Test if the store is tainted
        self.assertEqual(len(self.store.getSyncDomains()), 4, 'The store does not reflect the proper tainted status (True)')
    
    def testGetValues(self):
        if bool(self.store._data) is False: # Check if data is and empty dictionary:
            logger.debug('Populating "{}" with data...'.format(self.store))
            self.testSetValues()
            
            
#         from freedm.utils.formatters import printPrettyDict
#         printPrettyDict(self.store._data)
#         return

        tests = [
                 # TOKEN, DEFAULT, EXPECTED RESULT, EXPECTED TYPE, ITEM COUNT
                 ('daemon', None, None, dict, 1),
                 ('daemon.rpc', None, None, dict, 2),
                 ('daemon.rpc.port', None, 5555, int, None),
                 ('daemon.rpc.address', None, 'host.internet', str, None),
                 ('random.model.name', None, 'Moe', str, None),
                 ('person.maidenname', None, 'Bouvier', str, None),
                 ('person.haircolor', None, 'blue', str, None),
                 ('person', None, None, dict, 2),
                 ('dummy.test1', None, None, dict, 3),
                 ('dummy.test1.[].details', None, None, list, 3),
                 ('dummy.test1.[].details.name', None, ['Maggie', 'Bart', 'Lisa'], list, 3),
                 ('dummy.test1.4.details.name', None, 'Maggie', str, None),
                 ('dummy.test1.4.details', None, None, dict, None),
                 ('dummy.test5.struct.struct.struct.struct', None, [], list, None),
                 ('dummy.test6', None, [], list, 1),
                 ('dummy.test6.[].word',  None, None, None, None),
                 ('dummy.test6.[]',  None, [{'0': 'Servus'}], list, None),
                 ('dummy.test6.[].0',  None, {'0': 'Servus'}, dict, None),
                 ('dummy.test6.[].0.0',  None, 'Servus', str, None),
                 ('dummy.test6.0.0', None, 'Servus', str, None),
                 ('dummy.test7.4', None, 'Hallo', str, None),
                 ('dummy.test8.[]', None, None, list, 2),
                 ('dummy.test8.0.1', None, 'One', str, None),
                 ('dummy.test8.[].0', None, [None, 'One'], list, None),
                 ('dummy.test8.1.0', None, 'Zero', str, None),
                 ('dummy.test8.1.0', 'Default', 'Zero', str, None),
                 ('dummy.test8.1.100', 'Default', None, str, None),
                 ('dummy.+', None, None, list, 9),
                 ('person.+', None, [{'haircolor': 'blue'}, {'maidenname': 'Bouvier'}], list, 2),
                 ('daemon.+', None, [{'rpc': {'address': 'host.internet', 'port': 5555}}], list, 1),
                 ('daemon.rpc.+', None, [{'address': 'host.internet'}, {'port': 5555}], list, 2),
                 ('dummy.test1.+', None, [{'details': {'name': 'Lisa'}}, {'details': {'name': 'Maggie'}}, {'details': {'name': 'Bart'}}], list, 3),
                 ('dummy.test1.+.details.name', None, ['Bart', 'Lisa', 'Maggie'], list, 3),
                 ('dummy.test1.+.details.+', None, [{'name': 'Lisa'}, {'name': 'Maggie'}, {'name': 'Bart'}], list, 3),
                 ('dummy.test1.+.+.name', None, [{'details': 'Maggie'}, {'details': 'Bart'}, {'details': 'Lisa'}], list, 3),
                 ('dummy.test1.+.details.name', None, ['Bart', 'Lisa', 'Maggie'], list, 3),
                 ('dummy.test9.+', None, [[1, 2, 3], ['A', 'B', 'C']], list, 2),
                 ('dummy.test9.+.0', None, [1, 'A'], list, 2),
                 ('dummy.test9.+.+', None, [[1, 2, 3], ['A', 'B', 'C']], list, 2),
                 ('dummy.test2.+.role.name', None, ['Luke', 'Darth', 'Han'], list, 3),
                 ('dummy.test2.+.+.name', None, [{'role': 'Luke'}, {'role': 'Darth'}, {'role': 'Han'}], list, 3),
                 ('dummy.test2.+.+.age', None, [{'role': 30}, {'role': 60}, {'role': 40}], list, 3),
                 ('dummy.test2.+.role.+', None, [{'age': 30, 'lastname': 'Skywalker', 'name': 'Luke'}, {'age': 60, 'lastname': 'Vader', 'name': 'Darth'}, {'age': 40, 'lastname': 'Solo', 'name': 'Han'}], list, 3),
                ]
        
        # Test returned values
        logger.debug('Test returned data values...')
        for token, rdefault, rvalue, rtype, rcount in tests:
            try:
                # Get value
                logger.debug('Getting value for token "{}"'.format(token))
                result = self.store.getValue(token, rdefault)
                check = rvalue or rdefault
                
                # Check result
                if check:
                    if isinstance(check, list):
                        self.assertTrue(any(map(lambda v: v in result, check)), 'The returned value for "{}" does not equal "{}"'.format(token, check))
                    elif isinstance(check, list):
                        self.assertTrue(json.dumps(result) == json.dumps(check), 'The returned value for "{}" does not equal "{}"'.format(token, check))
                    else:
                        self.assertEqual(result, check, 'The returned value for "{}" does not equal "{}"'.format(token, check))
                if rtype:
                    self.assertTrue(isinstance(result, rtype), 'The returned value for "{}" is not of the type "{}"'.format(token, rtype))
                if rcount:
                    if isinstance(result, dict):
                        self.assertEqual(len(result.keys()), rcount, 'The returned value count for "{}" is "{}" instead of "{}"'.format(token, len(result.keys()), rcount))
                    elif isinstance(result, list):
                        self.assertEqual(len(result), rcount, 'The returned value count for "{}" is "{}" instead of "{}"'.format(token, len(result), rcount))
            except Exception as e:
                logger.critical('Failure when getting value for token "{}" ({})'.format(token, e))
                raise e
            
    def testSyncValues(self):
        import time
        if bool(self.store._data) is False: # Check if data is and empty dictionary:
            logger.debug('Populating "{}" with data...'.format(self.store))
            self.testSetValues()
        
        # Sync data
        try:
            # Set an artificial sync delay for testing the sync process 
            delay = 0.3
            start_delay = 0.15
            interval = len(self.store.getAllDomains())
            
            # Set max sync threads to 2
            self.store._sync_max_threads = 2
            
            # Get amount of syncWorkers
            sync_workers = self.store._sync_max_threads if self.store._sync_max_threads <= interval else interval
            
            # We set the private variable to True to see more sync actions going on (Test works also with setting it again to False)
            self.store._persistent = True
            
            # Override the store's _syncDomain with an artificial delay
            def testSyncDomain(self, domain, path):
                time.sleep(delay)
                domain.clearTainted()
            self.store._syncDomain = type(self.store._syncDomain)(testSyncDomain, self.store)
            
            # Make sure we sync parallel
            self.store._sync_parallel = True
                 
            # Start parallel syncing
            logger.debug('Testing parallel syncing of store "{}"...'.format(self.store))
            start = time.time()
            self.store.sync()
            end = time.time()
                 
            # Assert that we synced parallel
            self.assertTrue(delay*(interval/sync_workers) <= end-start <= delay*(interval/sync_workers)+1, 'The parallel syncing of the Memory store needed less or more time than expected')
                 
            # Now enable a sequential sync
            self.store._sync_parallel = False
                 
            # Start sequential syncing
            logger.debug('Testing sequential syncing of store "{}"...'.format(self.store))
            start = time.time()
            self.store.sync(force=True)
            end = time.time()
                 
            # Assert that we synced sequentially
            self.assertTrue(interval*delay <= end-start <= interval*delay+1, 'The sequential syncing of the Memory store needed less or more time than expected')
                 
            # Reset behaviour
            self.store._sync_parallel = True
               
            # Start multiple syncing
            logger.debug('Testing multiple syncing of store "{}"...'.format(self.store))
            start = time.time()
            for i in range(0,3):
                time.sleep(start_delay)
                self.store.sync(force=True)
            end = time.time()    
            # Assert that we synced parallel
            self.assertTrue(3*(delay*(interval/sync_workers)+start_delay) <= end-start <= 3*(delay*(interval/sync_workers)+start_delay) + 1, 'The multiple syncing of the Memory store needed less or more time than expected')
            
            # Start concurrent sync
            logger.debug('Testing concurrent syncing of store "{}"...'.format(self.store))
            start = time.time()
            sync1 = Thread(target=self.store.sync, name='Sync1', kwargs={'force': True})
            sync2 = Thread(target=self.store.sync, name='Sync2', kwargs={'force': True})
            sync3 = Thread(target=self.store.sync, name='Sync3', kwargs={'force': True})
            sync1.start()
            time.sleep(start_delay)
            sync2.start()
            time.sleep(start_delay)
            sync3.start()
            while sync1.isAlive() or sync2.isAlive() or sync3.isAlive():
                time.sleep(start_delay)
            end = time.time()
            
            # Assert that we synced in threads
            #print(delay*(interval/sync_workers)+start_delay*2 , end-start , delay*(interval/sync_workers)+start_delay*4)
            self.assertTrue(delay*(interval/sync_workers) <= end-start <= delay*(interval/sync_workers)+start_delay*4, 'The threaded syncing of the Memory store needed less or more time than expected')
            
        except Exception as e:
            logger.critical('Failed to sync store "{}" ({})'.format(self.store, e))
            raise e
        
        # Assert that store domains got synced
        self.assertEqual(len(self.store.getSyncDomains()), 0, 'The following store domains were not properly synced: ({})'.format(', '.join(self.store.getSyncDomains())))
        

# Test the memory store
class IniFileStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logger.info('Starting unittest: {}'.format(cls.__name__))
        try:
            cls.testpath = '/tmp/ini-' + getRandomString()
            shutil.rmtree(cls.testpath, ignore_errors=True)
            os.mkdir(cls.testpath)
        finally:
            cls.store = data.IniFileStore(name='IniStore', alias='ini', path=cls.testpath, filetype='.config')
        
        # TODO: Prepare data and schema
    
    @classmethod    
    def tearDownClass(cls):
        logger.info('Ending unittest: {}'.format(cls.__name__))
        try:
            cls.store.releaseHandle()
            cls.store = None
        finally:
            shutil.rmtree(cls.testpath, ignore_errors=True)
    
    def testStoreConfig(self):
        self.assertEqual(self.store.alias, 'Ini', 'Store alias is not "Ini"')
        self.assertEqual(self.store.name, 'IniStore', 'Store name is not "IniStore"')
        self.assertEqual(self.store.filetype, 'config', 'Store filetype is not "config"')
        self.assertEqual(self.store.path, self.testpath, 'Store path is not "{}"'.format(self.testpath))
        self.assertEqual(self.store.persistent, True, 'Store must not be persistent')
        self.assertEqual(self.store.writable, True, 'Store must be writable')
        self.assertEqual(self.store.synced, False, 'Store must not be synced')
        self.assertFalse(self.store._iohandle is None, 'Store should have no iohandle')
        
    def testDefaultValues(self):
        pass
    
    def testSetValues(self):
        pass
    
    def testGetValues(self):
        pass

# Test the data manager
class DataManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logger.info('Starting unittest: {}'.format(cls.__name__))
        try:
            cls.testpath = '/tmp/data-' + getRandomString()
            shutil.rmtree(cls.testpath, ignore_errors=True)
            os.mkdir(cls.testpath)
        finally:
            cls.manager = data.DataManager(cls.testpath)
    
    @classmethod   
    def tearDownClass(cls):
        logger.info('Ending unittest: {}'.format(cls.__name__))
        try:
            cls.manager.release()
            cls.manager = None
        finally:
            shutil.rmtree(cls.testpath, ignore_errors=True)

    def testPathLocation(self):
        self.assertTrue(os.path.exists(self.testpath), 'Data manager path "{}" does not exist'.format(self.testpath))
        self.assertEqual(self.testpath, str(self.manager.path), 'Data manager path "{}" does not equal correct path "{}"'.format(self.manager.path, self.testpath))
        
    def testStoreRegistration(self):
        # Create store
        memorystore = data.MemoryStore(name='MemoryCache', alias='cache')
        
        # Assert that the registration works
        self.assertTrue(self.manager.registerStore(memorystore), 'Store "{}" could not be registered'.format(memorystore))
        self.assertTrue(self.manager.registerStore(data.IniFileStore(**{
                                                                        'name': 'Configuration',
                                                                        'alias': 'config',
                                                                        'filetype': 'config',
                                                                        'synced': True
                                                                        })), 'Store "{}" could not be registered'.format('IniFileStore'))
        
        # Assert that we cannot register the same store twice
        self.assertFalse(self.manager.registerStore(memorystore))
        
        # Assert that the store has been probably registered
        self.assertTrue(memorystore.alias in self.manager.__stores, 'Registered store does not appear in __stores attribute')
        self.assertTrue(hasattr(self.manager, 'getCache'), 'Getter for store "{}" not created'.format(memorystore))
        self.assertTrue(hasattr(self.manager, 'setCache'), 'Setter for store "{}" not created'.format(memorystore))
        
        # Assert that the unregistration works
        self.assertTrue(self.manager.unregisterStore('cache'), 'Could not unregister store "{}"'.format(memorystore))
        
        # Assert that the unregistration does not work twice
        self.assertFalse(self.manager.unregisterStore(memorystore), 'Could unregister store "{}" twice'.format(memorystore))
        
    def testStoreLookup(self):
        pass
    
    def testStoreQuery(self):
        pass