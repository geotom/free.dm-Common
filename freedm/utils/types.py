'''
A utility class providing static methods for data type checks.
The preferred way of type checking is to simply use variables in try
blocks and catch type non-conformity in except blocks. But for cases where
prior type checking is the better approach, this utility class provides a set of
type checking methods.
@author: Thomas Wanderer
'''

# Imports
from typing import Any


class TypeChecker:

    @staticmethod
    def is_integer(obj: Any) -> bool:
        '''
        Checks if a number is an integer or if a string represents an integer
        '''
        if type(obj) == str:
            return obj.isdigit()
        else:
            return isinstance(obj, int)

    @staticmethod
    def is_float(obj: Any) -> bool:
        '''
        Checks if a number is a float or a string represents a float
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
    def is_boolean(obj: Any) -> bool:
        '''
        Checks if an object is a boolean
        '''
        return type(obj) == bool

    @staticmethod
    def is_numerical(cls, obj: Any) -> bool:
        '''
        Checks if a string represents a number (a float or integer)
        '''
        try:
            if cls.is_float(obj):
                return True
            elif cls.is_integer(obj):
                return True
            else:
                return False
        except Exception:
            return False

    @staticmethod
    def is_digit(obj: Any) -> bool:
        '''
        Checks if a string represents only digits (e.g. "12345")
        '''
        try:
            return str(obj).isdigit()
        except Exception:
            return False

    @staticmethod
    def is_string(obj: Any) -> bool:
        '''
        Checks if the object is a string
        '''
        return isinstance(obj, str)

    @staticmethod
    def is_tuple(obj: Any) -> bool:
        '''
        Checks if the object is a tuple
        '''
        return isinstance(obj, tuple)

    @staticmethod
    def is_list(obj: Any) -> bool:
        '''
        Checks if the object is a list
        '''
        return isinstance(obj, list)

    @staticmethod
    def is_dict(obj: Any) -> bool:
        '''
        Checks if the object is a dictionary
        '''
        return isinstance(obj, dict)

    @staticmethod
    def is_function(obj: Any) -> bool:
        '''
        Checks if the object is a function
        '''
        return hasattr(obj, '__call__')

    @staticmethod
    def is_alpha(string: str) -> bool:
        '''
        Checks if a string contains only alphabetical characters
        '''
        try:
            return string.isalpha()
        except Exception:
            return False

    @staticmethod
    def get_exact_type(obj: Any) -> str:
        '''
        Returns the object's type together with full module path
        '''
        try:
            return f'{obj.__class__.__module__}.{obj.__class__.__name__}'
        except Exception:
            try:
                return obj.__class__.__name__
            except Exception:
                return None

    @classmethod
    def is_exact_type(cls, obj: Any, obj_type: str) -> bool:
        '''
        Checks if the object is of a specific type name
        '''
        try:
            return cls.get_exact_type(obj) == obj_type
        except Exception:
            return False

    @staticmethod
    def is_iterable(obj: Any) -> bool:
        '''
        Checks if the object is iterable
        '''
        return hasattr(obj, '__iter__')
