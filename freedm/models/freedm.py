'''
Defaults
@author: Thomas Wanderer
'''

network = {
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
            'description': 'The free.dm network name',
            'default': 'free.dm'
            },
        'domain': {
            'type': 'string',
            'description': 'The free.dm network domain',
            'default': 'free.dm'
            }
        },
    'required': [
        'name',
        'domain'
        ],
    'additionalProperties': False
    }

master = {
    'type': 'object',
    'properties': {
        'address': {
            'type': 'string',
            'description': 'The free.dm master address',
            'default': 'master.free.dm'
            }
        },
    'required': ['address'],
    'additionalProperties': False
    }

router = {
    'type': 'object',
#            'properties': {
#                           'address': {'type': 'string', 'description': 'The free.dm master address', 'default': 'master.free.dm'}
#                           },
#            'required': ['address'],
#            'additionalProperties': False
    }