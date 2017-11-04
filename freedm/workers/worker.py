# -*- coding: utf-8 -*-
'''
The generic workers class. A workers is a sub-module of a daemon dealing with a specific task.
A workers can be a background process, invoked periodically, by event or manually. A workers class must 
also expose an action interface to the daemon allowing to query it via the daemon query mode.
@author: Thomas Wanderer
'''

class GenericWorker(object):
    pass

# Can we define argparsers with parent references for submodules?
#https://docs.python.org/2/library/argparse.html#parents