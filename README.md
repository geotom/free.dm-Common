# free.dm
A secure small cloud of private networks + web access & exposed services.

## free.dm Common
The core framework of free.dm used across all of its modules. 
This repository implements the foundation of the different free.dm nodes and their communication channels.
free.dm nodes will play different roles in their network but will share the same communication foundation on top of which specific functionality is implemented. This repository hosts the Python based modules for setting up a basic node role.

### Current state
The current state of the project is being a playground for testing different architectural approaches and communication frameworks while already providing some base classes. Under consideration is the use of:

* [RPyC](https://rpyc.readthedocs.io/en/latest/)
* [Raet](https://github.com/RaetProtocol/raet)
