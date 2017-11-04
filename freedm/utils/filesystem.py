'''
This module provides filesystem related utility methods
@author: Thomas Wanderer
'''

# Imports
import os
import time

class FilesystemObserver(object):
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
    def __init__(self, path, filetypes=None, handler=None, recursive=None):
        # Imports
        import logging
        
        # Get logger
        self.logger = logging.getLogger(str(os.getpid()))
        
        # Set path attribute
        if not os.path.exists(path):
            raise('(Path "{}" does not exist)'.format(path))
        else:
            self._path = path
            
        # Set filetype attribute
        if filetypes is not None: 
            for e in map(lambda ft: ft.split('.', 1)[-1], (filetypes,) if isinstance(filetypes, str) else (filetypes if isinstance(filetypes, list) else ())):
                self._extensions.append('*.{}'.format(e))
                
        # Set optional handler
        if handler is not None:
            self._handler = handler
        
        # Set recursive flag
        if isinstance(recursive, bool):
            self._recursive = recursive
    
    # Start & stop the observing
    def start(self):
        '''
        Start observing the path
        '''
        # Imports
        from contextlib import contextmanager
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, PatternMatchingEventHandler
        except ImportError as e:
            print('Missing dependency ({}): Please install via "pip install watchdog"'.format(e))
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
        
    def stop(self):
        '''
        Stop observing the path
        '''
        if self._watchdog is not None:
            self._watchdog.stop()
            self._watchdog.join()
            self._watchdog = None
        
    # Abstract file event handlers
    def onFileModified(self, event):
        '''
        Abstract method executed when a file is modified
        :param watchdog.events.FileModifiedEvent event: The filesystem event
        '''
        if self.__class__.__name__ != 'FilesystemObserver':
            self.logger.debug('Class "{}" does not implement the "onFileModified" method'.format(self.__class__.__name__))
        else:
            self.logger.info('File "{}" modified'.format(event.src_path))
            
    def onFileCreated(self, event):
        '''
        Abstract method executed when a file is created
        :param watchdog.events.FileCreatedEvent event: The filesystem event
        '''
        if self.__class__.__name__ != 'FilesystemObserver':
            self.logger.debug('Class "{}" does not implement the "onFileModified" method'.format(self.__class__.__name__))
        else:
            self.logger.info('File "{}" created'.format(event.src_path))
            
    def onFileDeleted(self, event):
        '''
        Abstract method executed when a file is deleted
        :param watchdog.events.FileDeletedEvent event: The filesystem event
        '''
        if self.__class__.__name__ != 'FilesystemObserver':
            self.logger.debug('Class "{}" does not implement the "onFileModified" method'.format(self.__class__.__name__))
        else:
            self.logger.info('File "{}" deleted'.format(event.src_path))
            
    def onFileMoved(self, event):
        '''
        Abstract method executed when a file is moved
        :param watchdog.events.FileMovedEvent event: The filesystem event
        '''
        if self.__class__.__name__ != 'FilesystemObserver':
            self.logger.debug('Class "{}" does not implement the "onFileModified" method'.format(self.__class__.__name__))
        else:
            self.logger.info('File "{}" moved to "{}"'.format(event.src_path, event.dest_path))