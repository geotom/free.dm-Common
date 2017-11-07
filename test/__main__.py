'''
This module creates a laboratory suite from individual laboratory cases
@author: Thomas Wanderer
'''
 
# Imports
import unittest
import sys
from pathlib import Path

# Test imports
import __init__


# Add tests from test directory and run
def run():
    # Get laboratory cases
    loader = unittest.TestLoader()
    tests = []
    for module in Path(__file__).resolve().parents[0].iterdir():
        if module.suffix == '.py' and not module.stem.startswith('__'):
            # Import & get the module
            __import__(module.stem, locals(), globals())
            module = sys.modules[module.stem]
              
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