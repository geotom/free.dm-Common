'''
This module creates a laboratory suite from individual laboratory cases
@author: Thomas Wanderer
'''

# Imports
import unittest
import sys
import os
import logging
from pathlib import Path


# Path
path = Path(__file__)

# Add import path
sys.path.append(path.parents[1])
sys.path.append('/home/tommi/Projekte/Privat/free.dm/Project/free.dm-Common/freedm')
for p in sys.path:
    print(p)

from freedm.utils import logger

# Run tests
def run():
    # Get laboratory cases
    loader = unittest.TestLoader()
    tests = []
    for module in os.listdir(path.parents[0]):
        if module[-3:] == '.py' and not module.startswith('__'):
            # Import & get the module
            __import__(module[:-3], locals(), globals())
            module = sys.modules[module[:-3]]
            # Load laboratory cases from module
            tests.append(loader.loadTestsFromModule(module))
              
    # Create laboratory suite
    suite = unittest.TestSuite(tests)
      
    # Run tests
    runner = unittest.TextTestRunner()
    return runner.run(suite)
 
# Main
if __name__ == "__main__":
    run()