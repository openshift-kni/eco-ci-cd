#!/usr/bin/env python3
'''
Ansible dynamic inventory script.

This script generates an Ansible inventory by scanning a specified directory
(hostvars_dir) for filenames.

    usage: build-inventory.py [-h] [-d HOSTVARS_DIR] [--list | --host HOST]
'''

import os
import argparse
import json
import sys

def get_inventory():
    '''Builds and returns the Ansible inventory structure.

    Initializes a base inventory and populates 'masters' and 'workers' groups
    by listing files in the directory specified by the globally defined `args.hostvars_dir`.
    All filenames found are added as keys to `_meta.hostvars` with an empty
    dictionary, registering them as hosts.

    Returns:
        dict: A dictionary representing the Ansible inventory.
    '''
    inventory = {
            'all': {
                'children': [
                    'ungrouped',
                    'nodes',
                    'bastions',
                    'vm_hosts'
                ]
            },
            'nodes': {
                'children': [
                    'masters'
                ]
            },
            'masters': {
                'hosts': []
            },
            'bastions': {
                'hosts': [
                    'bastion'
                ]
            },
            'hypervisors': {
                'hosts': [
                    'hypervisor'
                ]
            },
            'vm_hosts': {
                'children': [
                    'hypervisors'
                ]
            },
            "_meta": {
                "hostvars": {
            },
        }
    }
    workers = {'hosts': [] }

    for filename in os.listdir(args.hostvars_dir):
        inventory['_meta']["hostvars"][filename] =  {}

        if filename.startswith('master'):
            inventory['masters']['hosts'].append(filename)

        elif filename.startswith('worker') and os.path.isfile(os.path.join(args.hostvars_dir, filename)):
            workers['hosts'].append(filename)

    if workers['hosts']:
        inventory['workers'] = workers
        inventory["nodes"]["children"].append("workers")

    return inventory

def get_host_vars(hostname, inventory_data):
    '''Retrieves host-specific variables for a given hostname.

        Args:
            hostname (str): The name of the host.
            inventory_data (dict): The complete inventory data structure,
            which should contain a `_meta.hostvars` section.

        Returns:
            dict: A dictionary of variables for the host. Returns an empty
                dictionary if the host is not found or has no variables
                defined in `_meta.hostvars`.
    '''
    return inventory_data.get("_meta", {}).get("hostvars", {}).get(hostname, {})

def main():
    inventory_data = get_inventory()

    if args.list:
        print(json.dumps(inventory_data, indent=2))

    elif args.host:
        host_vars = get_host_vars(args.host, inventory_data)
        print(json.dumps(host_vars, indent=2))
    else:
        print(json.dumps(inventory_data, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ansible Dynamic Inventory")
    parser.add_argument('-d', '--hostvars_dir', default="./inventories/ocp-deployment/host_vars/", help="Path to the inventory directory")
    parser.add_argument('--list', action='store_true', help="List all groups and hosts")
    parser.add_argument('--host', help="Get all the variables about a specific host")
    args = parser.parse_args()
    
    if os.environ.get("HOSTVAR_DIR"):
        args.hostvars_dir = os.environ.get("HOSTVAR_DIR")

    if os.path.exists(args.hostvars_dir) and os.path.isdir(args.hostvars_dir):
        pass
    else:
        print(f"Host variables directory '{args.hostvars_dir}' does not exist or is not a directory.")
        sys.exit(1)

    main()