'''
This is a central file for defining global variables used across free.dm modules.
A heavy use of global variables is not advised but in certain cases it is necessary or acceptable.
@author: Thomas Wanderer
'''

MODE            = 'product'         # Possible values: 'product', 'staging', 'development'
VERBOSITY       = 3                 # Translates to level "logging.WARN = 30"
DATA            = './config/'       # Default data storage
VERSION         = 0
ERROR           = None              # Set by script