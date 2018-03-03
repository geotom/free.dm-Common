'''
This module provides concurrency related utility methods based on asyncio
@author: Thomas Wanderer
'''

# Imports
import asyncio
try:
    import uvloop
except ImportError:
    uvloop = None
from typing import Iterable, Any, Callable, Coroutine, Tuple, Type, Optional
from concurrent.futures import ThreadPoolExecutor

# free.dm Imports
from freedm.utils.types import TypeChecker as checker
from freedm.utils.exceptions import freedmBaseException


def getLoop(policy: Optional[Type[asyncio.AbstractEventLoopPolicy]]=None) -> asyncio.AbstractEventLoop:
    '''
    Returns the loop for the current context (thread/process).
    If a loop has been already created, it will return this one.
    In a new thread where where no loop yet exists it creates a new loop
    with the optionally passed loop policy. If no policy is provided this 
    tries to create a fast uvloop (dependent on availability) or one with the default policy.
    :param asyncio.AbstractEventLoopPolicy policy: An optional loop policy
    :returns: Asyncio loop
    :rtype: asyncio.AbstractEventLoop
    '''
    try:
        if isinstance(policy, asyncio.AbstractEventLoopPolicy):
            preferred_policy = policy
        elif uvloop:
            preferred_policy = uvloop.EventLoopPolicy()
        if asyncio.get_event_loop_policy() is not preferred_policy:
            asyncio.set_event_loop_policy(preferred_policy)
    except Exception as e:
        raise freedmAsyncLoopCreation(f'Cannot set policy: "{e}"')
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    except Exception as e:
        raise freedmAsyncLoopCreation(e)
    finally:
        def handle_exception(loop, context):
            raise freedmAsyncLoopException(context['exception'])
        if not loop.get_exception_handler():
            loop.set_exception_handler(handle_exception)
        return loop
    
    
class freedmAsyncLoopCreation(freedmBaseException):
    '''
    Gets thrown when no asyncio loop can be created
    '''
    template = 'Cannot create Asyncio loop ({error})'
    

class freedmAsyncLoopException(freedmBaseException):
    '''
    Gets thrown when we catch an exception in the loop
    '''
    def template(self, error):
        return f'Caught async loop exception "{error.__class__.__name__}" ({error})'


def runConcurrently(function: Callable, tasks: Iterable[Any], *args, max_threads: int=None, timeout: int=None) -> None:
    '''
    This method runs a given non-coroutine function concurrently for each task item by the help
    of the asyncio module and a concurrent executor. The executor creates a thread 
    for each task item if no max_threads is set and cleans up its resources afterwards.
    :param func function: The function to run
    :param Iterable tasks: A list/tuple of items for each of them we run the function.
    The items will also serve as argument to the function. Each further *args parameter will be used for the function
    :param int max_threads: Limit the number of threads. By default we create a thread for each item
    :param int timeout: Limit the execution time by a timeout
    '''   
    # Check requirements: A function and a non-empty list
    if checker.isFunction(function) and checker.isIterable(tasks) and len(tasks) > 0:
        # First get this threads loop or create a new one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            asyncio.set_event_loop(loop)
                
        # Create a worker pool for each "task" in the list (which are to be executed parallel        
        workers: List[Coroutine[ThreadPoolExecutor, Callable, Tuple]] = []
        with ThreadPoolExecutor(max_workers=max_threads if checker.isInteger(max_threads) else len(tasks)) as executor:
            # Create coroutine threads
            for t in tasks:
                workers.append(loop.run_in_executor(executor, function, *tuple([t] + list(args))))
                
            # Run all release operations in parallel
            if workers:
                loop.run_until_complete(asyncio.wait(workers, timeout=timeout))