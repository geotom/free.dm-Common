'''
A class representing the server role of the communication system between free.dm nodes.
@author: Thomas Wanderer
'''

# Imports
from raet.road import stacking
from raet.road import estating

class Channel(object):
    '''
    The RAET communication channel functioning as main estate
    '''
    
    
    #See https://docs.saltstack.com/en/latest/topics/transports/raet/programming_intro.html
    
#     udp_stack = stacking.StackUdp(ha=('127.0.0.1', 7870))
#     r_estate = estating.Estate(stack=stack, name='foo', ha=('192.168.42.42', 7870))
#     msg = {'hello': 'world'}
#     udp_stack.transmit(msg, udp_stack.estates[r_estate.name])
#     udp_stack.serviceAll()
    
#     stack = stacking.RoadStack(
#                                 name='lord', 
#                                 main=True
#                                 )
#     timer = Timer(duration=0.5)
#     timer.restart()
#     while not timer.expired:
#         stack.serviceAll()


"""
I see an idle salt-master (2 subscribed minions) using more CPU than seems reasonable. All (7) processes are spinning on select and recvfrom. Select is being called with a 10ms timeout. Together they are keeping the CPU about 10% busy.
I assume this in from the ioflo udp code: ioflo/aio/udp/udping.py (where it seems to just mark the socket non-blocking and spin calling recvfrom).
Is there some way to make these worker processes more CPU friendly?

--> 

Unfortunately it's how ioflo works by design. But there's a config option controlling ioflo timer period applicable for both master and minion configs:

ioflo_period: 0.1

If you increase this value the process gets slower on network operations handling but eats less cpu on idle. For example if you'll set it to 1 the max time minion will need to respond to test.ping is about 4 seconds (1 ping job seq/resp + 1 findjob req/resp). Try to change it and test.

--> 

Ioflo is a state machine based on timer ticks. It's design assumes no blocking operations in the business logic.

So in your case when Salt is idle most of the time you can either increase the timer period with ioflo_period or try to use ZeroMQ or TCP transport based on Tornado.

--> 

The zmq_behavior setting might be useful!
"""