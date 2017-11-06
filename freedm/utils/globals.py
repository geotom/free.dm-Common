'''
This is a central file for defining global variables used across free.dm modules.
A heavy use of global variables is not advised but in certain cases it is necessary or acceptable.
@author: Thomas Wanderer
'''

MODE : str          = 'product'         # Possible values: 'product', 'staging', 'development', 'debug'
VERBOSITY : int     = 3                 # Translates to level "logging.WARN = 30"
DATA : str          = './config/'       # Default data storage
VERSION : str       = '0.1.0'           # A Semantic Versioning number
ERROR               = None              # Set by script