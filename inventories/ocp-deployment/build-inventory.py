#!/usr/bin/env python3

import os
import yaml
import sys

if len(sys.args) < 2:
    print(f"""
        ERROR: please add host_vars path as argument to the script
        
        Usage: {sys.args[0]} < host_vars path> 
        """)
    os.exit(1)
hostvars_dir = sys.argv[1] # path to the host_vars dir
dest_file = "deploy-ocp-hybrid-multinode.yml"
masters = []
workers = []

if os.path.exists(hostvars_dir) and os.path.isdir(hostvars_dir):
    for filename in os.listdir(hostvars_dir):
        if filename.startswith('master') and os.path.isfile(os.path.join(hostvars_dir, filename)):
            masters.append(filename)
        elif filename.startswith('worker') and os.path.isfile(os.path.join(hostvars_dir, filename)):
            workers.append(filename)

masters.sort()
workers.sort()

output_yaml = {
    'nodes': {
        'children': {
            'masters': {},
            'workers': {}
        }
    },
    'masters': {
        'hosts': {}
    },
    'workers': {
        'hosts': {}
    },
    'bastions': {
        'hosts': {
            'bastion': {}
        }
    },
    'hypervisors': {
        'hosts': {
            'hypervisor': {}
        }
    },
    'vm_hosts': {
        'children': {
            'hypervisors': {}
        }
    }
}

output_yaml['masters']['hosts'] = {node: {} for node in masters}
output_yaml['workers']['hosts'] = {node: {} for node in workers}


with open(dest_file, 'w') as outfile:
    yaml.dump(output_yaml, outfile, sort_keys=False)

print(f"inventory {dest_file} file created successfully.")
