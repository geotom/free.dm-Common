'''
Module methods to retrieve default values from their JSON schema 
and to validate values against their JSON schema.
@author: Thomas Wanderer
'''

# Imports
import logging
import os
from pydoc import locate
try:
    from jsonschema import validate
    from jsonschema.exceptions import ValidationError, SchemaError
except ImportError as e:
    print('Missing dependency ({}): Please install via "pip install jsonschema"'.format(e))

# free.dm Imports
from freedm.utils.formatters import ellipsis

# Utility methods
def __buildDefaultValue(schema):
    '''
    This private method builds a default data structure 
    object from the provided value schema.
    :param object schema: The JSON schema definition
    :returns object: The default data structure or ``None``
    '''
    try:
        # If the schema describes a list, we will just return an empty list
        if schema.get('type') == 'array':
            return []
        
        # If the schema describes an object, we will traverse the schema to get default values for each required property
        elif schema.get('type') == 'object':
            # All described properties
            properties = schema.get('properties') or {}
            # Only the required properties
            possible = (schema.get('properties') or {}).keys()
            required = schema.get('required')
            default = {}
            
            # If a required properties are defined, only build default objects for them
            if required and properties:
                possible = set(required).intersection(set(possible))
            
            # Get the default value for each possible/required property
            for key in possible:
                p = properties[key]
                if p:
                    # Traverse further to build sub-propertiy objects
                    if p.get('type') in ('array', 'object'):
                        default.update({key: __buildDefaultValue(p)})
                    # Build the default property object
                    else:
                        default.update({key: properties[key].get('default')})
                else:
                    # There is no default value for this property
                    default.update({key: None})
                    
            # Return built default object
            return default
        
        # If it is just an object without "type" attribute
        elif isinstance(schema, dict):
            # If it is just an object but with a "type" attribute
            if schema.get('type'):
                return schema.get('default')
            else:
                default = {}
                for k in schema.keys():
                    default.update({k: __buildDefaultValue(schema.get(k))})
                return default
        
        # Else return nothing
        else:
            return None
    except:
        return None
    
def __prepareCollectionObject(data):
    '''
    This private option makes a copy of the provided data structure and
    replaces collection objects (=dictionaries with numeric keys) in them
    by a list representation. This is required to validate such data structures 
    against a JSON schema which only knows the schema element type "array".
    :param object data: The nested data structure
    '''
    if isinstance(data, list) or isinstance(data, dict):
        # Work on a copy of the provided data
        dataobject = data.copy()
        
        # The recursive traverse option
        def traverseDataObject(obj):
            try:
                # Transform in a list if is a "numerical dict" 
                if isinstance(obj, dict) and len(obj.keys()) > 0 and all(k.isdigit() for k in obj.keys()):
                    obj = [v for k,v in obj.items()]
                # Traverse this object
                if isinstance(obj, list):
                    i = []
                    for element in obj:
                        i.append(traverseDataObject(element))
                    obj = i
                elif isinstance(obj, dict):
                    for element in obj:
                        obj[element] = traverseDataObject(obj[element])
                else:
                    pass
                # Return the object
                return obj
            except:
                pass
                    
        # Traverse the data
        dataobject = traverseDataObject(dataobject)
        
        # Return the prepared data
        return dataobject
    else:
        return data
    
# Validation function
def isValidValue(token, value):
    '''
    Checks if the provided value passes a validation check against the token's
    model schema. Please refer to http://json-schema.org/documentation.html or 
    https://spacetelescope.github.io/understanding-json-schema for more insights on JSON schema.
    :param str token: The token
    :param value: The value
    :returns: Validation result and the value or a validation failure cause instead
    :rtype bool:
    '''
    result = getValidatedValue(token, value, exception=True)
    if isinstance(result, ValidationError):
        return False, result.message
    else:
        return True, value

# Get Value functions
def getDefaultValue(token):
    '''
    Returns a default value for the token if found in the model schema. Please refer to 
    http://json-schema.org/documentation.html or
    https://spacetelescope.github.io/understanding-json-schema for more insights on JSON schema.
    :param str token: The key token default value if found
    :returns: The default value for this token or ``None`` if not found
    '''
    try:
        # Get the domain and key from the provided token
        try:
            domain, key = str(token).split('.', 1)
        except ValueError:
            domain = str(token).split('.', 1)[0]
            key = False
        
        # Get the default class
        cls = locate('{}.{}'.format(__package__, domain))
        
        # Find a default value in the domain by key
        if cls and key:
            tokens = key.split('.')
            
            # Just one token key
            if len(tokens) == 1 and tokens[0] in ((cls.get('properties') or cls) if isinstance(cls, dict) else cls.__dict__):
                # Get data schema
                schema = (cls.get('properties') or cls)[tokens.pop(0)] if isinstance(cls, dict) else getattr(cls, tokens.pop(0))
                # Return "[]" for an array or build a default object
                if schema.get('type') == 'array':
                    return []
                elif schema.get('type') == 'object':
                    return __buildDefaultValue(schema)
                else:
                    return schema.get('default')
                
            # More than one token key
            if len(tokens) > 1 and tokens[0] in ((cls.get('properties') or cls) if isinstance(cls, dict) else cls.__dict__):
                # Get data schema
                schema = (cls.get('properties') or cls)[tokens.pop(0)] if isinstance(cls, dict) else getattr(cls, tokens.pop(0))
                # Traverse through subschemas for each token
                for i, t in enumerate(tokens):
                    # Get index position
                    last = (len(tokens) - i) == 1
                    
                    # 1st possibility: Value is a single member of a collection
                    if t.isdigit() and schema.get('type') == 'array':
                        obj = schema.get('items')
                        if last and isinstance(obj, dict):
                            # Lets immediately return a default object built from the properties
                            return __buildDefaultValue(obj)
                            
                    # 2nd possibility: Value is member of a collection      
                    elif t == '[]' and schema.get('type') == 'array':
                        return []
                        
                    # 3rd possibility: Value refers to a single property, and is not member of a collection
                    else:
                        # Try to get sub-schema
                        obj = schema.get(t)

                        # Did not work? Try sub-schema definitions (properties/items)
                        if obj is None:
                            p = schema.get('properties')
                            i = schema.get('items')
                            if p:
                                obj = p.get(t)
                            elif i:
                                if isinstance(i, dict):
                                    obj = i.get('properties').get(t)
                        # If the last schema describes an array, return "[]" as default
                        if last and obj.get('type') == 'array':
                            return []
                        elif last and obj.get('type') == 'object':
                            return __buildDefaultValue(obj)
                                    
                    # Set found schema or raise an exception
                    if obj is not None:
                        schema = obj
                    else:
                        raise Exception

                # In case we provide a token referring to a collection, the default is always "[]"
                if schema is None and '[]' in token:
                    return []
                # Try to return an existing default value
                elif schema:
                    return schema.get('default') or None
                else:
                    raise LookupError
        
        # In case we have just the domain, build a default object for the whole domain
        elif cls:
            schema = {}
            if isinstance(cls, dict):
                for key in [k for k in cls.keys() if k[:1] != '_']:
                    schema.update({key: cls.get(key)})
            else:
                for key in [k for k in cls.__dict__.keys() if k[:1] != '_']:
                    schema.update({key: getattr(cls, key)})
            return __buildDefaultValue(schema)
        
        # If no class is found at all, make sure we raise an exception and return "None"
        else:
            raise Exception
    except Exception:
        logger = logging.getLogger(str(os.getpid()))
        logger.warn('Default value for token "{}" not defined'.format(token))
    
    # If no default value has been returned so far, we finally return None
    return None
    
def getValidatedValue(token, value, **kwargs):
    '''
    Returns the provided value if it passed a validation laboratory against the token's
    model schema or ``None`` if the laboratory failed. Please refer to 
    http://json-schema.org/documentation.html or 
    https://spacetelescope.github.io/understanding-json-schema for more insights on JSON schema.
    :param str token: The token
    :param value: The value
    :returns value: The provided value if valid or ``None`` if validation failed
    '''
    # Only for private functions that require an exception instead of ``None`` as return value
    exception = bool(kwargs.get('exception')) or False
    
    try:
        # This will be a temporarily copy of the value to validate (in a prepared form)
        dataobject = None
        
        # Get the domain and key from the provided token
        try:
            domain, key = str(token).split('.', 1)
        except ValueError:
            domain = str(token).split('.', 1)[0]
            key = False
            
        # Get the default class
        cls = locate('{}.{}'.format(__package__, domain))
        
        # Validate a value against a sub-schema (of a schema module in freedm.models)
        if cls and key:
            tokens = key.split('.')
            
            # In case of the following tokens: "model.+"
            if len(tokens) >= 1 and tokens[0] == '+':
                # Recursively check the values with a token where '+' is substituted
                checks = []
                for v in value:
                    k = next(iter(v))
                    checks.append(getValidatedValue(
                                                    '{}.{}'.format(domain, k),
                                                    v[k],
                                                    exception=True
                                                    )
                                  )
                # Check for an exception
                if any(isinstance(e, Exception) for e in checks):
                    value = ([e for e in checks if isinstance(e, Exception)] if exception else None)
            
            # In case of the following tokens: "model.property"
            elif len(tokens) >= 1 and tokens[0] in ((cls.get('properties') or cls) if isinstance(cls, dict) else cls.__dict__):
                # Get data schema
                schema = (cls.get('properties') or cls)[tokens.pop(0)] if isinstance(cls, dict) else getattr(cls, tokens.pop(0))
                
                # Traverse through subschemas for each token
                for i, t in enumerate(tokens):
                    # Get index position
                    last = (len(tokens) - i) == 1
                    
                    # Try to find a sub-schema definition for current key token
                    try:
                        # 1st possibility: Value is member of a collection
                        if (t.isdigit() or t == '[]') and schema.get('type') == 'array':
                            # We use the previous schema again
                            if last and schema.get('type') == 'array':
                                obj = schema
                            # Try to find the correct items or properties sub-schema  
                            else:
                                obj = schema.get('items')

                        # 2nd possibility: Value is a wildcard collection. Iteratively check each item
                        elif t == '+':
                            # Recursively check the values with a token where '+' is substituted
                            checks = []
                            token_prev_part = '{}.{}'.format(domain, '.'.join(key.split('.')[:i+1]))
                            token_next_part = '.'.join(key.split('.')[i+2:] if not last else '')
                            token_placeholder = '.'.join([p for p in [token_prev_part, '{}', token_next_part] if p != '' ])

                            if hasattr(value, '__iter__'):
                                for v in value:
                                    # If the values are dictionaries
                                    if isinstance(v, dict):
                                        # If the "+" was the last key token and the dictionary has more than one key like {a:1, b:2,...}, 
                                        # then we should not substitute the "+" but rather remove and check the whole structure
                                        if last and len(v.keys()) > 1:
                                            checks.append(getValidatedValue(token_placeholder.replace('.{}', ''), v, exception=True))
                                        # Do a normal check by substituting the "+ for instance by "[]" or the one and only key in the dictionary
                                        else:
                                            # Get the key of the value
                                            value_key = next(iter(v))
                                            # 1st check: Assume we can replace "+" by the value key
                                            check_token = token_placeholder.format(value_key)
                                            check_result = getValidatedValue(check_token, v[value_key], exception=True)
                                            # 2nd check: Assume we must replace "+" by a collection "[]"
                                            if (isinstance(check_result, list) and any(isinstance(r, Exception) for r in check_result)) or isinstance(check_result, Exception):
                                                check_token = token_placeholder.format('[]')
                                                # Save 2nd check result
                                                checks.append(getValidatedValue(check_token, [v], exception=True))
                                            # 1st check has succeeded
                                            else:
                                                checks.append(check_result)
                                    # If the values are lists
                                    elif isinstance(v, list):
                                        check_token = token_placeholder.format('[]')
                                        checks.append(getValidatedValue(check_token, v, exception=True))
                                    # If the values are for instance strings
                                    else:
                                        check_token = token_placeholder.format('[]')
                                        check_result = getValidatedValue(check_token, v, exception=True)
                                        checks.append(check_result)
                                        if isinstance(check_result, Exception):
                                            break # Do not check more than one single character of a string when the token already fails
                            else:
                                check_token = token_placeholder.format('[]')
                                checks.append(getValidatedValue(check_token, value, exception=True))
                            
                            # Check for an exception
                            if any(isinstance(e, Exception) for e in checks):
                                value = ([e for e in checks if isinstance(e, Exception)] if exception else None)
                            # We stop at this moment as we just validated the wildcard results separately in recursive steps
                            return
                        
                        # 3rd possibility: Value refers to a single property, and is not member of a collection
                        else:
                            # Try to get sub-schema
                            obj = schema.get(t)
                            # Did not work? Try sub-schema definitions (properties/items)
                            if obj is None:
                                p = schema.get('properties')
                                i = schema.get('items')
                                if p:
                                    obj = p.get(t)
                                elif i:
                                    if isinstance(i, dict):
                                        obj = i.get('properties').get(t)
                                        
                            # This is a last check for special situation where we refer to one item in a previous collection "[]"
                            # The key token also must be a digit number and no schema found yet.
                            if obj is None and '[]' in token and t.isdigit():
                                obj = schema
                        
                        # Set found schema or raise an exception
                        if obj is not None:
                            schema = obj
                        else:
                            raise Exception

                    # Or try using the last schema we found for the previous token
                    except:
                        if schema.__contains__('additionalProperties') and schema.get('additionalProperties') is False:
                            # We reset the value to None because new additional properties are not allowed
                            if exception:
                                value = ValidationError('No validation schema found for token "{}" and new schema properties not allowed by model')
                            else:
                                value = None
                                raise UserWarning('No validation schema found for token "{}" and model "{}" does not allow new schema properties'.format(token, domain))
                        else:
                            if schema.get('type') == 'object':
                                # We warn the user but as we have additionalProperties allowed (object's default), we continue using the value with the new token
                                raise UserWarning('No validation schema found for token "{}". Define model schema in "freedm.models.{}.py"'.format(token, domain))
                            else:
                                # Validate against the last schema we found
                                raise ValidationError('Token "{}" refers to invalid sub-element to property of type "{}"'.format(t, schema.get('type')))
                
                # Prepare the data (To get rid of dictionaries with numeric keys)
                dataobject = __prepareCollectionObject(value)
                
                # Make sure that single members of a collection (=Token must contain a number) are properly packed for validation 
                if schema.get('type') == 'array' and any(d in token for d in '0123456789') and not isinstance(dataobject, list):
                    # Value is a single collection element, we need to pack it in a list
                    validate([dataobject], schema)
                # Make sure that all single items in a collection are each individually checked against the schema
                elif schema.get('type') != 'array' and '[]' in token and isinstance(dataobject, list):
                    # Validate each element individually   
                    for v in dataobject:
                        validate(v, schema)
                # The normal case where a value is checked against its schema
                else:
                    validate(dataobject, schema)
            else:
                raise UserWarning('No validation schema found for token "{}.{}.*". Define schema in "freedm.models.{}.py"'.format(domain, tokens[0], domain))

        # Validate against a root schema, for instance just "model", without any further key like "model.?" (schema module in freedm.models)
        elif cls:
            # The dictionary is the schema
            if isinstance(cls, dict):
                validate(value, cls)
            # Build a schema for each property we find in the class
            else:
                # Build one JSON schema of all schema properties
                schema = {}
                for key in [k for k in cls.__dict__.keys() if k[:1] != '_']:
                    schema.update({key: getattr(cls, key)})
                # We validate a data structure (object)
                if isinstance(value, dict):
                    # Try validating the domain data with the found schemas
                    s_keys = schema.keys()
                    v_keys = value.keys()
                    s_diff = list(set(s_keys) - set(v_keys))
                    v_diff = list(set(v_keys) - set(s_keys))
                    if len(s_diff) > 0:
                        raise UserWarning('Domain data does not define values for: {}'.format(', '.join(s_diff)))
                    elif len(v_diff) > 0:
                        raise ValidationError('Domain data should not contain these additional values ({})'.format(', '.join(v_diff)))
                    else:
                        for v in v_keys:
                            # Prepare the data (To get rid of dictionaries with numeric keys)
                            dataobject = __prepareCollectionObject(value[v])
                            # Validate
                            validate(dataobject, schema[v])
                # We validate just one single value
                else:
                    validate(value, schema)
        # If no class is found at all, make sure we raise an exception and return "None"
        else:
            raise UserWarning('No validation schema found for token "{0}.*". Define schema in "freedm.models.{0}.py"'.format(domain))
    except UserWarning as uw:
        logger = logging.getLogger(str(os.getpid()))
        logger.debug(uw)
    except SchemaError as se:
        logger = logging.getLogger(str(os.getpid()))
        logger.warn('Validation schema for token "{}" is malformed ({})'.format(token, se.message))
    except ValidationError as ve:
        try:
            if not exception:
                logger = logging.getLogger(str(os.getpid()))
                logger.warn('{} "{}" validation with value "{}" failed ({})'.format('Schema' if token.isalpha() else 'Sub-Schema', token, ellipsis(str(value), 40), ve.message))
        finally:
            # Make sure a "None" will be returned on Validation errors in any case
            value = None if not exception else ve
    except Exception as e:
        pass
    finally:
        # Delete the temporary data object, created for validation
        del dataobject
        # Return the value in any case (None if a ValidationError occured)
        return value