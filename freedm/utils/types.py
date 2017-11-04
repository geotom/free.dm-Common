'''
A utility class providing static methods for data type checks.
The preferred way of type checking is to simply use variables in try
blocks and catch type non-conformity in except blocks. But for cases where 
prior type checking is the better approach, this utility class provides a set of
type checking methods.

@author: tommi
'''

class TypeChecker(object):
    
    @staticmethod
    def isInteger(obj):
        '''
        Checks if a number is an integer or if 
        a string represents an integer
        :param object obj: Any object
        :rtype: bool
        '''
        if type(obj) == str:
            return obj.isdigit()
        else:
            return isinstance(obj, int)
    
    @staticmethod
    def isFloat(obj):
        '''
        Checks if a number is a float
        or a string represents a float
        :param object obj: Any object
        :rtype: bool
        '''
        if type(obj) == str:
            result = False
            if obj.count('.') == 1:
                if obj.replace('.', '').isdigit():
                    result = True
            elif obj.count(',') == 1:
                if obj.replace(',', '').isdigit():
                    result = True
            return result
        else:
            return isinstance(obj, float)
    
    @staticmethod
    def isBoolean(obj):
        '''
        Checks if an object is a boolean
        :param object obj: Any object
        :rtype: bool
        '''
        return type(obj) == bool
    
    @staticmethod
    def isNumerical(cls, obj):
        '''
        Checks if a string represents a number (a float or integer)
        :param object obj: Any object
        :rtype: bool
        '''
        try:
            if cls.isFloat(obj):
                return True
            elif cls.isInteger(obj):
                return True
            else:
                return False
        except:
            return False
    
    @staticmethod
    def isDigit(obj):
        '''
        Checks if a string represents only digits (e.g. "12345")
        :param object obj: Any object
        :rtype: bool
        '''
        try:
            return str(obj).isdigit()
        except:
            return False
    
    @staticmethod  
    def isString(obj):
        '''
        Checks if the object is a string
        :param object obj: Any object
        :rtype: bool
        '''
        return isinstance(obj, str)
    
    @staticmethod  
    def isTuple(obj):
        '''
        Checks if the object is a tuple
        :param object obj: Any object
        :rtype: bool
        '''
        return isinstance(obj, tuple)
    
    @staticmethod  
    def isList(obj):
        '''
        Checks if the object is a list
        :param object obj: Any object
        :rtype: bool
        '''
        return isinstance(obj, list)
    
    @staticmethod  
    def isDict(obj):
        '''
        Checks if the object is a dictionary
        :param object obj: Any object
        :rtype: bool
        '''
        return isinstance(obj, dict)

    @staticmethod  
    def isFunction(obj):
        '''
        Checks if the object is a function
        :param object obj: Any object
        :rtype: bool
        '''
        return hasattr(obj, '__call__')
    
    @staticmethod  
    def isAlpha(string):
        '''
        Checks if a string contains only alphabetical characters
        :param str string: A string
        :rtype: bool
        '''
        try:
            return string.isalpha()
        except:
            return False
    
    @staticmethod  
    def getExactType(obj):
        '''
        Returns the object's type together with full module path
        :param object obj: Any object
        :returns: The objects's type
        :rtype: str
        '''       
        try:
            return '{}.{}'.format(obj.__class__.__module__, obj.__class__.__name__)
        except:
            try:
                return obj.__class__.__name__
            except:
                return None

    @classmethod  
    def isExactType(cls, obj, obj_type):
        '''
        Checks if the object is of a specific type name
        :param object obj: Any object
        :param str obj_type: The full name of the type including the module path
        :rtype: bool
        '''
        try:
            return cls.getExactType(obj) == obj_type
        except:
            return False
        
    @staticmethod
    def isIterable(obj):
        '''
        Checks if the object is iterable
        :param obj: Any object
        :rtype: bool
        '''
        return hasattr(obj, '__iter__')