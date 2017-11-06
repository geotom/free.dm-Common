'''
This module creates a laboratory suite from individual laboratory cases
@author: Thomas Wanderer
'''

# Imports
import unittest, os, sys, logging

# Add import path
sys.path.append(os.path.realpath(__file__).replace(os.path.basename(__file__), '../../'))

# Run tests
def run():
    # Get laboratory cases
    loader = unittest.TestLoader()
    tests = []
    for module in os.listdir(os.path.dirname(__file__)):
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