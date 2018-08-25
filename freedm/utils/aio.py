'''
This module provides concurrency related utility methods based on asyncio
@author: Thomas Wanderer
'''

# Imports
import sys
import signal
import asyncio
try:
    import uvloop
except ImportError:
    uvloop = None
from typing import Iterable, Any, Callable, Coroutine, Tuple, Type, Optional
from concurrent.futures import ThreadPoolExecutor

# free.dm Imports
from freedm.utils import logging
from freedm.utils.types import TypeChecker as checker
from freedm.utils.exceptions import freedmBaseException


def get_loop(policy: Optional[Type[asyncio.AbstractEventLoopPolicy]]=None) -> asyncio.AbstractEventLoop:
    '''
    Returns the loop for the current context (thread/process).
    If a loop has been already created, it will return this one.
    In a new thread where where no loop yet exists it creates a new loop
    with the optionally passed loop policy. If no policy is provided this
    tries to create a fast uvloop (dependent on availability) or one with the default policy.
    '''
    try:
        preferred_policy = asyncio.get_event_loop_policy()
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
            e_message = context.get('message')
            e_future = context.get('future')
            e_error = context.get('exception')
            e_trace = e_error.__traceback__ if e_error else None
            if e_future:
                e_code = e_future.get_stack()[0].f_code
                e_error = freedmAsyncLoopException(
                    f'''Async exception "{e_error or e_message}" in "{e_future._coro.__qualname__}" ({e_code.co_filename}:{e_code.co_firstlineno})'''
                )
            else:
                e_error = freedmAsyncLoopException(f'''Async exception "{e_error or e_message}"''')
            e_type = type(e_error)
            sys.excepthook(e_type, e_error, e_trace)
        if not loop.get_exception_handler():
            loop.set_exception_handler(handle_exception)
        return loop


class BlockingContextManager:
    '''
    An async context manager which is safe from being
    interrupted by certain signals like SIGINT (Keyboard
    interupt) or SIGTERM. It will wait for the "with-block"
    to finish before resuming the SIGNAL by its original
    registered handler.
    '''
    # List of respected signals
    signals = (
        signal.SIGINT,
        signal.SIGTERM
    )

    # Logger
    logger = None

    async def __aenter__(self):
        '''
        In case we don't call this context manager as awaitable,
        then setup new temporary signal handlers, save the original handlers
        and block any of the defined signals until the context finishes
        '''
        # Setup logger
        if not self.logger:
            self.logger = logging.getLogger()

        # Check if we are awaited, thus not use as context manager (by checking the caller history
        i = 1
        caller = None
        while i < 50 and (caller == '__aenter__' or not caller):
            caller = sys._getframe(i).f_code.co_name
            i += 1
            if caller == '__await__':
                return

        self._signal_received = {}
        self._old_handlers = {}

        for sig in self.signals:
            # Save original handlers while this context is running
            self._signal_received[sig] = False
            self._old_handlers[sig] = signal.getsignal(sig)

            # Intermediate (safe) signal handler
            def signal_context_handler(s, frame, sig=sig):
                self._signal_received[sig] = (s, frame)
                print()
                self.logger.debug(f'Signal {signal.Signals(sig).name} delayed by blocking context "{self.__class__.__name__}"')

            # Replace the original handler by the handler defined by this context manager
            self._old_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, signal_context_handler)

        # Return context
        return self

    async def __aexit__(self, *args):
        '''
        If the __aenter__ has stored old signal handlers, then
        reinstate them and resume with the caught signal
        '''
        try:
            self._old_handlers
            for sig in self.signals:
                # Reinstate the original handler and continue with the received frame
                signal.signal(sig, self._old_handlers[sig])
                if self._signal_received[sig] and self._old_handlers[sig]:
                    self.logger.debug(f'Signal {signal.Signals(sig).name} resumed')
                    self._old_handlers[sig](*self._signal_received[sig])
        except Exception:
            return


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
        return f'Caught async loop exception "{error.__class__.__name__ if not isinstance(error, str) else error}" ({error})'


def run_concurrently(function: Callable, tasks: Iterable[Any], *args, max_threads: int=None, timeout: int=None) -> None:
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
    if checker.is_function(function) and checker.is_iterable(tasks) and len(tasks) > 0:
        # First get this threads loop or create a new one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            asyncio.set_event_loop(loop)

        # Create a worker pool for each "task" in the list (which are to be executed parallel
        workers: List[Coroutine[ThreadPoolExecutor, Callable, Tuple]] = []
        with ThreadPoolExecutor(max_workers=max_threads if checker.is_integer(max_threads) else len(tasks)) as executor:
            # Create coroutine threads
            for t in tasks:
                workers.append(loop.run_in_executor(executor, function, *tuple([t] + list(args))))

            # Run all release operations in parallel
            if workers:
                loop.run_until_complete(asyncio.wait(workers, timeout=timeout))
