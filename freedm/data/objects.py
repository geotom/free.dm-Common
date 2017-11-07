



        

    
        
# class oldConfigurationObject(object):
#     
#     _backend = None
#     
#     __defaults = {}
#     
#     __configuration = {}
#     
#     _tainted = False
#     
#     # Init
#     def __init__(self, configuration = None, defaults = None):
#         
#         # Set any provided configuration values or default structures
#         if checker.isDict(configuration):
#             self.__configuration = configuration
#         if checker.isDict(defaults):
#             self.__defaults = defaults
#         else:
#             self.__defaults = dict(
#                                   daemon = dict(port = 5000, address = 'localhost', debug = False),
#                                   freedm = dict(network = 'free.dm')
#                                   )
#         
#     def set(self, tokenized_key, value):
#         '''
#         Sets a hierarchically tokenized configuration parameter. For instance "pool.server1.port"
#         '''
#         pass
#         
#     def get(self, tokenized_key):
#         '''
#         Returns a hierarchically tokenized configuration parameter. For instance "pool.server1.port"
#         '''
#          
#         # Split the configuration into its tokens, then check for the value of the  attribute
#         keys = tokenized_key.split('.')
#         steps = 0
# 
#         # First: Search for the value in the configuration object
#         cursor = self.__configuration
#         for k in keys:
#             steps += 1
#             # Check if we access a list
#             if k.endswith(']'):
#                 k = k.split('[')[0]
#                 i = int(k.split('[')[1][0:-1])
#             # Check if key exists
#             if k in cursor:
#                 cursor = cursor[k]
#                 if checker.isList(cursor) and checker.isInteger(i):
#                     cursor = cursor[i]
#                     i = None
#                 if not checker.isIterable(cursor) or checker.isString(cursor):
#                     # Return here with "None" if we have lesser tokens than in the query
#                     if(steps > 0 and steps < len(keys)):
#                         # Return "None" here without a second check for default values
#                         return None
#                     elif(steps > 0 and steps == len(keys)):
#                         # Return the value without a second check for default values
#                         return cursor
#             else:
#                 cursor = None;
#                 break
#         
#         # Second: Search for the value in the default structure
#         if cursor == None:
#             cursor = self.__defaults
#             for k in keys:
#                 # Check if we access a list
#                 if k.endswith(']'):
#                     k = k.split('[')[0]
#                     i = int(k.split('[')[1][0:-1])
#                 # Check if key exists
#                 if k in cursor:
#                     cursor = cursor[k]
#                     if checker.isList(cursor) and checker.isInteger(i):
#                         cursor = cursor[i]
#                         i = None
#                     if not checker.isIterable(cursor):
#                         break
#                 else:
#                     cursor = None
#                     break
# 
#         # Return the value
#         return cursor