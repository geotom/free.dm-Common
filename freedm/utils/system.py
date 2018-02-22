'''
General utilities to retrieve structured system information of the OS environment
@author: Thomas Wanderer
'''

# Imports
import os
import sys
import platform
import psutil
import struct
import subprocess
from typing import Dict, Union, Optional, List

# free.d Imports
from freedm.utils.exceptions import freedmUnsupportedOS

# OS specific imports
try:
    import grp
except ImportError as e:
    raise freedmUnsupportedOS(e)
try:
    import pwd
except ImportError as e:
    raise freedmUnsupportedOS(e)


def getHardwarePlatform() -> str:
    '''
    Returns the hardware platform name or alternatively info about the CPU
    :returns: Hardware platform
    :rtype: str
    '''
    cpu         = None
    mhz         = None
    hw          = None
    nulldevice  = open(os.devnull, 'w')
    try:
        for line in subprocess.check_output('dmidecode -t baseboard', shell=True, stderr=nulldevice).decode('utf-8').split('\n'):
            if line.strip().startwith('Manufacturer'):
                hw = [line.strip().split(': ')[1]]
            if line.strip().startwith('Product Name'):
                hw.append(line.strip().split(': ')[1])
            if line.strip().startwith('Version'):
                hw.append(line.strip().split(': ')[1])
            hw = ' '.join(hw)
    except:
        try:
            for line in subprocess.check_output('cat /proc/cpuinfo', shell=True, stderr=nulldevice).decode('utf-8').split('\n'):
                if line.startswith('model name') and cpu is None:
                    cpu = line.split(': ')[1].strip()
                elif line.startswith('cpu MHz') and mhz is None:
                    mhz = line.split(': ')[1].strip()
            if cpu is not None and mhz is not None:
                if cpu == 'Geode(TM) Integrated Processor by AMD PCS' and mhz.startswith('498'):
                    hw = 'PC Engines Alix'
                elif cpu == 'AMD G-T40E Processor' and mhz.startswith('800'):
                    hw = 'PC Engines Apu'
                else:
                    hw = cpu
        except:
            hw = 'Unknown'
    return hw

def getSystemInfo(pid: Optional[int]=None) -> Dict[str, str]:
    '''
    Returns a dictionary with structured system information
    :param pid: An optional numeric process ID (default: This process ID)
    :returns: System information
    :rtype: dict
    '''
    
    # Build a dictionary with daemon info 
    info = dict(
        os          = f'{platform.system()} {" ".join(platform.dist()).strip()} ({platform.release()}, {platform.architecture()[0]})',
        platform    = getHardwarePlatform(),
        os_64       = platform.architecture()[0] == '64bit',
        py_64       = struct.calcsize('P') * 8 == 64,
        memory      = {},
        disks       = [],
        nics        = []
        )
    
    # Get memory information
    m = psutil.virtual_memory()
    s = psutil.swap_memory()
    info['memory'] = dict(
        mem_total     = round(m.total / float(1024), 1),
        mem_used      = round(m.total / float(1024), 1) - round(m.available / float(1024), 1),
        mem_free      = round(m.available / float(1024), 1),
        swap_total    = round(s.total / float(1024), 1),
        swap_used     = round(s.used / float(1024), 1),
        swap_free     = round(s.total / float(1024), 1)
        )
    
    # Get process information
    try:
        p = psutil.Process(pid or os.getpid())
        info['process'] = dict(
            script           = os.path.abspath(sys.argv[0]),
            directory        = os.path.abspath(os.path.curdir),
            pid              = p.pid,
            user             = p.username(),
            group            = getGroupByGid(p.gids().real),
            uid              = p.uids().real,
            gid              = p.gids().real,
            threads          = p.num_threads(),
            memory_rss       = round(p.memory_info().rss / float(1024 ** 2), 1),
            memory_vms       = round(p.memory_info().vms / float(1024 ** 2), 1),
            memory_rss_pct   = round(p.memory_percent(), 1),
            memory_vms_pct   = round(p.memory_percent(memtype='vms'), 1)
            )
    except psutil.NoSuchProcess:
        info['process'] = dict(
            pid              = None,
            user             = None,
            group            = None,
            uid              = None,
            gid              = None,
            threads          = None,
            memory_rss       = None,
            memory_vms       = None,
            memory_rss_pct   = None,
            memory_vms_pct   = None
            )
    
    # Get network information
    nic     = psutil.net_if_addrs()
    nic_c   = psutil.net_io_counters(pernic=True)
    nic_s   = psutil.net_if_stats()
    for n in nic:
        ni = dict(
            name      = n,
            addrs     = [],
            counter   = dict(nic_c[n]._asdict()),
            speed     = nic_s[n].speed,
            mtu       = nic_s[n].mtu,
            )
        for a in nic[n]:            
            ni['addrs'].append(dict(
                family  = a.family.name.replace('AF_', '').lower(),
                address = a.address,
                mask    = a.netmask,
                bcast   = a.broadcast,
                ptp     = a.ptp
                ))
        info['nics'].append(ni)
        
    # Get disk partitions
    for p in psutil.disk_partitions():
        info['disks'].append(dict(
            device        = p.device,
            mountpoint    = p.mountpoint,
            usage         = dict(psutil.disk_usage(p.mountpoint)._asdict())
            ))
        
    # Gather user info 
    info['user'] = getUserInfo()
    
    # Return the info
    return info

def getUserByUid(uid: Optional[int]=None) -> Optional[str]:
    '''
    Returns the user name for the provided user ID or script user
    :param uid: An optional numeric user ID (default: This script's user)
    :returns: User name
    :rtype: str
    '''
    if not uid: uid = os.getuid()
    if not isinstance(uid, int):
        return None
    return pwd.getpwuid(uid)[0]

def getUidByUser(user: Optional[str]=None) -> Optional[int]:
    '''
    Returns the numerical user ID for a user name 
    :param user: An optional user name (default: This script's user)
    :returns: User ID
    :rtype: int
    '''    
    if not user:
        return os.getuid()
    elif isinstance(user, str):
        return pwd.getpwnam(user)[2]
    else:
        return None
    
def getGroupByGid(gid: Optional[int]=None) -> Optional[str]:
    '''
    Returns the group name for the provided group ID or scritp user's primary group
    :param gid: An optional numeric group ID (default: This script's user primary group)
    :returns: Group name
    :rtype: str
    '''
    if not gid: gid = os.getgid()
    if not isinstance(gid, int):
        return None
    return grp.getgrgid(gid)[0]

def getGidByGroup(group: Optional[str]=None) -> Optional[int]:
    '''
    Returns the numerical group ID for a group name 
    :param group: An optional user name (default: This scripts user's primary group)
    :returns: Group ID
    :rtype: int
    '''    
    if not group:
        return os.getgid()
    elif isinstance(group, str):
        return grp.getgrnam(group)[2]
    else:
        return None
    
def getUserGroups(user: Optional[Union[int, str]]=None, numeric: bool=None) -> List[Union[int,str]]:
    '''
    Returns a list with all groups a user is member of
    :param user: An optional user name or numeric user ID (default: This script's user)
    :returns: User information
    :rtype: list
    '''
    if not user:
        user = os.getuid()
        
    groups = []
        
    try:
        user = pwd.getpwuid(user) if isinstance(user, int) else pwd.getpwnam(user)
        groups.append(user[3] if numeric else getGroupByGid(user[3]))
        groups = groups + [g[2] if numeric else g[0] for g in grp.getgrall() if user[0] in g.gr_mem]
    except:
        pass
    
    return groups
    
def getUserInfo(user: Optional[Union[int, str]]=None) -> Dict[str, Union[int,str]]:
    '''
    Returns a dictionary with structured user information
    :param user: An optional user name or numeric user ID (default: This script's user)
    :returns: User information
    :rtype: dict
    '''
    if not user:
        user = os.getuid()
        
    info = {
        'uid': user if isinstance(user, int) else None,
        'gid': None,
        'user': user if isinstance(user, str) else None,
        'group': None,
        'groups': None,
        'gecos': None,
        'path': None,
        'shell': None
        }
    
    try:
        user = pwd.getpwuid(user) if isinstance(user, int) else pwd.getpwnam(user)
        info['uid'] = user[2]
        info['gid'] = user[3]
        info['user'] = user[0]
        info['group'] = getGroupByGid(user[3])
        info['groups'] = [g[0] for g in grp.getgrall() if user[0] in g.gr_mem]
        info['gecos'] = user[4].split(',')
        info['path'] = user[5]
        info['shell'] = user[6]
    except:
        pass
    
    return info