'''
This module provides filesystem related utility methods
@author: Thomas Wanderer
'''

# Imports
import os
import time
import logging
from typing import Type, List, Union
from contextlib import contextmanager
from pathlib import Path
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEvent, FileSystemEventHandler, PatternMatchingEventHandler
except ImportError as e:
    from freedm.utils.exceptions import freedmModuleImport
    raise freedmModuleImport(e)


class FilesystemObserver:
    '''
    This class implements a filesystem monitor, observing changes to files within
    the provided directory path. The underlying monitoring capability is achieved by 
    using the cross-platform module "watchdog" (Which supports Unix, Windows, MacOS).
    
    :param str path: The directory path to observe
    :param str/list filetypes: One (str) or more (list) file extensions we should exclusively observe
    :param py:class::watchdog.events.FileSystemEventHandler handler: An optional event handler class replacing the default one of this class
    :param bool recursive: Set to ``True`` to also observe subdirectories
    '''
    
    # Attributes
    _path       = None
    _extensions = []
    _recursive  = False
    _handler    = None
    _watchdog   = None
    logger      = None
    
    # Init
    def __init__(self, path: Union[str, Path], filetypes: Union[str, List[str]]=None, handler: Type[FileSystemEventHandler]=None, recursive: bool=None):
        # Get logger
        self.logger = logging.getLogger(str(os.getpid()))
        
        # Set path attribute
        if not os.path.exists(path):
            raise(f'(Path "{path}" does not exist)')
        else:
            # Seems that the watchdog library requires a path in string format
            self._path = str(path)
            
        # Set filetype attribute
        if filetypes is not None: 
            for e in map(lambda ft: ft.split('.', 1)[-1], (filetypes,) if isinstance(filetypes, str) else (filetypes if isinstance(filetypes, list) else ())):
                self._extensions.append(f'*.{e}')
                
        # Set optional handler
        if handler is not None:
            self._handler = handler
        
        # Set recursive flag
        if isinstance(recursive, bool):
            self._recursive = recursive
    
    # Start & stop the observing
    def start(self) -> None:
        '''
        Start observing the path
        '''
        
        try:
            type(Observer)
        except:
            return
        
        # Subclass the Observer class to be able to interrupt the filesystem monitoring
        class InterruptibleObserver(Observer):
            def dispatch_events(self, *args, **kwargs):
                if not getattr(self, '_OBSERVER_PAUSED', False):
                    super().dispatch_events(*args, **kwargs)

            def pause(self):
                self._OBSERVER_PAUSED = True

            def resume(self):
                time.sleep(self.timeout)
                self.event_queue.queue.clear()
                self._OBSERVER_PAUSED = False

            @contextmanager
            def interruptObserver(self):
                # Interrupt the observer
                self.pause()
                # Yield from code executed in between
                try:
                    yield
                # We must resume the observer
                finally:
                    self.resume()
        
        # Define custom event listener
        if not isinstance(self._handler, FileSystemEventHandler):
            self._handler = type(
                'EventHandler',
                (PatternMatchingEventHandler, ),
                {
                    'patterns': self._extensions if len(self._extensions) > 0 else ('.*'),
                    'on_modified': self.onFileModified,
                    'on_created': self.onFileCreated,
                    'on_deleted': self.onFileDeleted,
                    'on_moved': self.onFileMoved
                    }
                )
        
        # Start observer
        if self._path is not None:
            eventhandler = self._handler(ignore_directories=True, case_sensitive=True)
            self._watchdog = InterruptibleObserver(timeout=1)
            self._watchdog.event_queue.maxsize = 0
            self._watchdog.schedule(eventhandler, path=self._path, recursive=self._recursive)
            self._watchdog.start()
        
    def stop(self) -> None:
        '''
        Stop observing the path
        '''
        if self._watchdog is not None:
            self._watchdog.stop()
            self._watchdog.join()
            self._watchdog = None
        
    # Abstract file event handlers
    def onFileModified(self, event: FileSystemEvent) -> None:
        '''
        Abstract method executed when a file is modified
        :param watchdog.events.FileModifiedEvent event: The filesystem event
        '''
        if self.__class__.__name__ != 'FilesystemObserver':
            self.logger.debug(f'Class "{self.__class__.__name__}" does not implement the "onFileModified" method')
        else:
            self.logger.info(f'File "{event.src_path}" modified')
            
    def onFileCreated(self, event: FileSystemEvent) -> None:
        '''
        Abstract method executed when a file is created
        :param watchdog.events.FileCreatedEvent event: The filesystem event
        '''
        if self.__class__.__name__ != 'FilesystemObserver':
            self.logger.debug(f'Class "{self.__class__.__name__}" does not implement the "onFileModified" method')
        else:
            self.logger.info(f'File "{event.src_path}" created')
            
    def onFileDeleted(self, event: FileSystemEvent) -> None:
        '''
        Abstract method executed when a file is deleted
        :param watchdog.events.FileDeletedEvent event: The filesystem event
        '''
        if self.__class__.__name__ != 'FilesystemObserver':
            self.logger.debug(f'Class "{self.__class__.__name__}" does not implement the "onFileModified" method')
        else:
            self.logger.info(f'File "{event.src_path}" deleted')
            
    def onFileMoved(self, event: FileSystemEvent) -> None:
        '''
        Abstract method executed when a file is moved
        :param watchdog.events.FileMovedEvent event: The filesystem event
        '''
        if self.__class__.__name__ != 'FilesystemObserver':
            self.logger.debug(f'Class "{self.__class__.__name__}" does not implement the "onFileModified" method')
        else:
            self.logger.info(f'File "{event.src_path}" moved to "{event.dest_path}"')