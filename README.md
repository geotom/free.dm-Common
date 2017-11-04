# free.dm
A secure small cloud of private networks + web access & exposed services

## free.dm Common
The core framework of free.dm used accross all of its modules. 
This repositoriy implements the foundation of the different free.dm nodes and their communication channels.
free.dm nodes will play different roles in their network but will share the same communication foundation on top of which specific functionality is implemented. This repository hosts the Python based modules for setting up a basic node role.

### Current state
The current this is more of a playground for testing different architectual approaches and communication frameworks. underconsideration are:

* [RPyC](https://rpyc.readthedocs.io/en/latest/)
* [Raet](https://github.com/RaetProtocol/raet)
