'''
General utilities to retrieve structured system information of the OS environment
@author: Thomas Wanderer
'''

# Imports
import os

def getHardwarePlatform():
    '''
    Returns the hardware platform name or alternatively info about the CPU
    :returns: Hardware platform
    :rtype: str
    '''
    import subprocess
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

def getSystemInfo(pid=os.getpid()):
    '''
    Returns a dictionary with structured system information
    :returns: System information
    :rtype: dict
    '''
    import platform, psutil, grp
    # Build a dictionary with daemon info 
    info = dict(
                os          = '{0} ({1}, {2})'.format(' '.join(platform.dist()), platform.release(), platform.architecture()[0]),
                platform    = getHardwarePlatform(),
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
    p = psutil.Process(pid)
    info['process'] = dict(
                           pid              = p.pid,
                           user             = p.username(),
                           group            = grp.getgrgid(p.gids().real)[0],
                           uid              = p.uids().real,
                           gid              = p.gids().real,
                           threads          = p.num_threads(),
                           memory_rss       = round(p.memory_info().rss / float(1024 ** 2), 1),
                           memory_vms       = round(p.memory_info().vms / float(1024 ** 2), 1),
                           memory_rss_pct   = round(p.memory_percent(), 1),
                           memory_vms_pct   = round(p.memory_percent(memtype='vms'), 1)
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
                                    )
                               )
        info['nics'].append(ni)
        
    # Get disk partitions
    for p in psutil.disk_partitions():
        info['disks'].append(dict(
                                  device        = p.device,
                                  mountpoint    = p.mountpoint,
                                  usage         = dict(psutil.disk_usage(p.mountpoint)._asdict())
                                  )
                             )   
    
    # Return info
    return info
    