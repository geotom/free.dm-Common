'''
Defaults
@author: Thomas Wanderer
'''

rpc = {
    'type': 'object',
    'properties': {
        'port': {
            'type': 'integer',
            'description': 'The RPyC socket port', 
            'default': 5000,
            'minimum': 1025,
            'maximum': 10000,
            'max': 1
            },
        'address': {
            'type': 'string',
            'description': 'The RPyC socket address', 
            'default': 'localhost',
            'max': 1
            }
        },
   'required': [
       'port',
       'address'
       ],
   'additionalProperties': False
   }

# database = {
#     'type': 'object',
#     'properties': {
#         'port': {
#             'type': 'integer',
#             'description': 'The PostgreSQL database port',
#             'default': 5432,
#             'minimum': 1025,
#             'maximum': 10000,
#             'max': 1
#             },
#         'address': {
#             'type': 'string',
#             'description': 'The PostgreSQL database address',
#             'default': 'localhost',
#             'max': 1
#             },
#         'user': {
#             'type': 'string',
#             'description': 'The database user\'s name', 
#             'default': 'freedm',
#             'max': 1
#             },
#         'password': {
#             'type': 'string',
#             'description': 'The database user\'s password',
#             'default': '',
#             'max': 1
#             }
#         },
#     'required': [
#         'port',
#         'address',
#         'user',
#         'password'
#         ],
#     'additionalProperties': False
#     }
 
 
# name = {'type': 'string', 'description': 'A persons name', 'enum': ['Hans', 'Peter', 'Alex', 'Michi'], 'default': 'Hans', 'max': 1}
# surname = {'type': 'string', 'description': 'A persons surname', 'max': 1, 'default': 'Meier'}
# child = {'type': 'string', 'description': 'A childs name', 'min': 0, 'max': 10}