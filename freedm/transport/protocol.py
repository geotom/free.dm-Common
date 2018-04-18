'''
This module defines a generic transport protocol to be used between servers and clients
Subclass from this class to create your own communication protocol.
@author: Thomas Wanderer
'''


class Protocol:
    
    version: None
    
    def supports(self):
        pass
    
    
# Sollten settings based sein, also settings das Protokoll verhalten beeinflussen
# 
# Base protocols
# 
# Protocols sollen rpc oder topic based sein, also entweder eine rpc API anbieten oder einfach nur ein Public subscribe anbieten
# 
# Brauchen evtl. Einen internen state?
#
# Sollten Zugriff auf verschiedene States haben wie:
#
# - Aktuelle Client Sessions
# -
# 
# Sollten Versioniert werden können
#
# Sollten zwischen Client und Server unterscheiden können
# 
# Standard dekoratoren für Services oder amdereechanismen sollten erlauben schnell ein Protokoll aufzusetzen.
# 
# Für unterschiedliche Einsatzzwecke. Einmal Unidirectional oder bidirektional.
# 
# Brauchen message queue und evtl. Ein adressier system