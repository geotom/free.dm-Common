'''
A small event class
@author: Thomas Wanderer
'''
# From http://stackoverflow.com/questions/1092531/event-system-in-python
class Event(list):
    """Event subscription.

    A list of callable objects. Calling an instance of this will cause a
    call to each item in the list in ascending order by index.

    Example Usage:
    >>> def f(x):
    ...     print 'f(%s)' % x
    >>> def g(x):
    ...     print 'g(%s)' % x
    >>> e = Event()
    >>> e()
    >>> e.append(f)
    >>> e(123)
    f(123)
    >>> e.remove(f)
    >>> e()
    >>> e += (f, g)
    >>> e(10)
    f(10)
    g(10)
    >>> del e[0]
    >>> e(2)
    g(2)

    """
    def __call__(self, *args, **kwargs):
        for f in self:
            f(*args, **kwargs)

    def __repr__(self):
        return "Event(%s)" % list.__repr__(self)
    
# From http://www.valuedlessons.com/2008/04/events-in-python.html    
class Event(IEvent):
    def __init__(self):
        self.handlers = set()

    def handle(self, handler):
        self.handler.add(handler)
        return self

    def unhandle(self, handler):
        try:
            self.handlers.remove(handler)
        except:
            raise ValueError("Handler is not handling this event, so cannot unhandle it.")
        return self

    def fire(self, *args, **kargs):
        for handler in self.handlers:
            handler(*args, **kargs)

    def getHandlerCount(self):
        return len(self.handlers)

    __iadd__ = handle
    __isub__ = unhandle
    __call__ = fire
    __len__  = getHandlerCount

class MockFileWatcher:
    def __init__(self):
        self.fileChanged = Event()

    def watchFiles(self):
        source_path = "foo"
        self.fileChanged(source_path)

def log_file_change(source_path):
    print "%r changed." % (source_path,)

def log_file_change2(source_path):
    print "%r changed!" % (source_path,)

watcher              = MockFileWatcher()
watcher.fileChanged += log_file_change2
watcher.fileChanged += log_file_change
watcher.fileChanged -= log_file_change2
watcher.watchFiles()

----------------

# http://python-utilities.readthedocs.io/en/latest/events.html

------------

https://github.com/riga/pymitter

from pymitter import EventEmitter

ee = EventEmitter()

# decorator usage
@ee.on("myevent")
def handler1(arg):
   print "handler1 called with", arg

# callback usage
def handler2(arg):
    print "handler2 called with", arg
ee.on("myotherevent", handler2)

# emit
ee.emit("myevent", "foo")
# -> "handler1 called with foo"

ee.emit("myotherevent", "bar")
# -> "handler2 called with bar"

-------------------

class EventManager:

    class Event:
        def __init__(self,functions):
            if type(functions) is not list:
                raise ValueError("functions parameter has to be a list")
            self.functions = functions

        def __iadd__(self,func):
            self.functions.append(func)
            return self

        def __isub__(self,func):
            self.functions.remove(func)
            return self

        def __call__(self,*args,**kvargs):
            for func in self.functions : func(*args,**kvargs)

    @classmethod
    def addEvent(cls,**kvargs):
        """
        addEvent( event1 = [f1,f2,...], event2 = [g1,g2,...], ... )
        creates events using **kvargs to create any number of events. Each event recieves a list of functions,
        where every function in the list recieves the same parameters.

        Example:

        def hello(): print "Hello ",
        def world(): print "World"

        EventManager.addEvent( salute = [hello] )
        EventManager.salute += world

        EventManager.salute()

        Output:
        Hello World
        """
        for key in kvargs.keys():
            if type(kvargs[key]) is not list:
                raise ValueError("value has to be a list")
            else:
                kvargs[key] = cls.Event(kvargs[key])

        cls.__dict__.update(kvargs)

#Create an event with no listeners assigned to it
EventManager.addEvent( eventName = [] )

#Create an event with listeners assigned to it
EventManager.addEvent( eventName = [fun1, fun2,...] )

#Create any number event with listeners assigned to them
EventManager.addEvent( eventName1 = [e1fun1, e1fun2,...], eventName2 = [e2fun1, e2fun2,...], ... )

#Add or remove listener to an existing event
EventManager.eventName += extra_fun
EventManager.eventName -= removed_fun

#Delete an event
del EventManager.eventName

#Fire the event
EventManager.eventName()

def hello(name):
    print "Hello {}".format(name)

def greetings(name):
    print "Greetings {}".format(name)

EventManager.addEvent( salute = [greetings] )
EventManager.salute += hello

print "\nInitial salute"
EventManager.salute('Oscar')

print "\nNow remove greetings"
EventManager.salute -= greetings
EventManager.salute('Oscar')


---------------------

https://pythonhosted.org/blinker/

-------------------------




