'''
This module provides concurrency related utility methods based on asyncio
@author: Thomas Wanderer
'''

# Imports
import asyncio
import uvloop
from typing import List, Any, Callable, Coroutine, Tuple
from concurrent.futures import ThreadPoolExecutor

# free.dm Imports
from freedm.utils.types import TypeChecker as checker


def runConcurrently(function: Callable, tasks: List[Any], *args, max_threads: int=None, timeout: int=None) -> None:
    '''
    This method runs a given non-coroutine function concurrently for each task item by the help
    of the asyncio module and a concurrent executor. The executor creates a thread 
    for each task item if no max_threads is set and cleans up its resources afterwards.
    :param func function: The function to run
    :param list tasks: A list of items for each of them we run the function.
    The items will also serve as argument to the function. Each further *args parameter will be used for the function
    :param int max_threads: Limit the number of threads. By default we create a thread for each item
    :param int timeout: Limit the execution time by a timeout
    '''   
    # Check requirements: A function and a non-empty list
    if checker.isFunction(function) and checker.isList(tasks) and len(tasks) > 0:
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