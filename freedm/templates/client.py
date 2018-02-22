'''
Templates used by daemon clients
@author: Thomas Wanderer
'''

DaemonInfo = '''{{role}} daemon ({{pid}}) running at <{{address}}:{{port}}>
   Version:\t\t{{version}}
   State:\t\t{{state}}
   Network:\t\t{{network}}
   Uptime:\t\tDaemon:  {{daemon_uptime}}
   \t\t\tSystem:  {{system_uptime}}

Environment
    User:\t\t{{process['user']}} (UID={{process['uid']}})
    Group:\t\t{{process['group']}} (GID={{process['gid']}})
    Script:\t\t{{process['script']}}
    Working directory:\t{{process['directory']}}
    Umask:\t\t

System status
   Linux:\t\t{{os}}
   Platform:\t\t{{platform}}
   Memory:\t\tRam:  {{ '{:>7}'.format((memory['mem_used']/1024)|round) }} MiB of {{ '{:>6}'.format((memory['mem_total']/1024)|round) }} MiB used
   \t\t\tSwap: {{ '{:>7}'.format((memory['swap_used']/1024)|round) }} MiB of {{ '{:>6}'.format((memory['swap_total']/1024)|round) }} MiB used
   Memory usage:\tRes:  {{ '{:>7}'.format(process['memory_rss']) }} MiB\t{{  '{:>6}'.format(process['memory_rss_pct'])  }}% used
   \t\t\tVms:  {{ '{:>7}'.format(process['memory_vms']) }} MiB\t{{  '{:>6}'.format(process['memory_vms_pct'])  }}% used
   Threads:\t\t{{ process['threads'] }} running threads
   Interfaces:\t\t{% for nic in nics %}{% if nic != nics[0] %}
   \t\t\t{% endif %}{{ nic['name'] }}\tSpeed: \t{{ nic['speed'] }} MB/s\n\t\t\t\tMTU: \t{{ nic['mtu'] }}\n\t\t\t\tData: \tSent= {{ '{:>7}'.format((nic['counter']['bytes_sent']/1024**2)|round(1)) }} Mib, Recv= {{ '{:>7}'.format((nic['counter']['bytes_recv']/1024**2)|round(1)) }} Mib{% for a in nic['addrs'] %}{% if a['family'] != 'packet' %}
   \t\t\t\t{{ '{:<7}'.format(a['family'] + ':') }}\tAdress: \t{{ a['address'] }}\n\t\t\t\t\tMask: \t\t{{ a['mask'] }}\n\t\t\t\t\tBroadcast: \t{{ a['bcast'] }}{% endif %}{% endfor %}\t\t\t{% endfor %}
   Disks:\t{% for disk in disks %}\t{{ '{:<15}'.format(disk['mountpoint']) }}\t{{ disk['device'] }}\t{{ '{:>6}'.format(disk['usage']['percent']) }}% used\n         \t{% endfor %}
Active monitor sessions ({{sessions|count}}){% if sessions|count > 0 %}
{{createTable([
            ('address', 'Address'),
            ('port', 'Port'),
            ('duration', 'Since'),
            ], 
            sessions, indention=3
            )}}{% endif %}
'''

ServerInfo = DaemonInfo + '''
Connected <{{network}}> routers ({{clients|count}}){% if clients|count > 0 %}
{{createTable([
            ('section', 'Section'),
            ('address', 'Address'),
            ('port', 'Port'),
            ('version', 'Version'),
            ('state', 'State'),
            ('duration', 'Since')
            ], 
            clients, indention=3
            )}}{% endif %}
'''

RouterInfo = DaemonInfo + '''
Connected free.dm routers ({{clients|count}})
   Section\tAddress\t\tPort\tSince\tVersion\tState{% if routers|count > 0 %}{% for router in routers %}\n   {{router['section']}}\t{{router['address']}}\t\t{{router['port']}}\t{{router['duration']}}{% endfor %}{% endif %}
'''