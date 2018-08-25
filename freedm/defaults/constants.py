'''
This is a central file for defining package default constant values used across free.dm modules.
@author: Thomas Wanderer
'''


# Possible values: 'product', 'staging', 'development', 'debug'
MODE: str = 'product'

# Translates to level "logging.WARN = 30"
VERBOSITY: int = 3

# Default data storage
DATA: str = './config/'

# A Semantic Versioning number
VERSION: str = '0.1.0'

# Set by script
ERROR = None