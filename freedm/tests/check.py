'''
This laboratory checks the functionality of the free.dm utils type checker module
@author: Thomas Wanderer
'''

# Imports
import unittest
import logging
import sys

# free.dm Imports
from freedm.utils.types import TypeChecker as checker


# Setup logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler(sys.stdout))

# Test type checking
class TypeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logger.info('Starting unittest: {}'.format(cls.__name__))
    
    @classmethod   
    def tearDownClass(cls):
        logger.info('Ending unittest: {}'.format(cls.__name__))
        
    def testAlphaStrings(self):
        tests = [
                 ['Hello', True],
                 ['Hello World', False],
                 [b'Hello', True],
                 ['Mažasančiųplūduriuojantisežero', True],
                 ['小鴨子湖面上漂浮著', True],
                 ['1小鴨子湖面上漂浮著', False],
                 ['user-name', False],
                 [1, False],
                 [1.2, False],
                 [{}, False],
                ]
        for t in tests:
            logger.debug('String "{}" is{}alphabetical'.format(t[0], ' ' if t[1] else ' not '))
            if t[1]:
                self.assertTrue(checker.isAlpha(t[0]), 'Testing alphanumeric strings failed for "{}"'.format(t[0]))
            else:
                self.assertFalse(checker.isAlpha(t[0]), 'Testing alphanumeric strings failed for "{}"'.format(t[0]))
