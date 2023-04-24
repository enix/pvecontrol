#!/usr/bin/env python

import os
import sys
import argparse
import confuse
import pprint
import urllib3
from prettytable import PrettyTable
from proxmoxer import ProxmoxAPI
from collections import OrderedDict
from humanize import naturalsize


configtemplate = {
    'clusters': confuse.Sequence(
        {
            'name': str,
            'host': str,
            'user': str,
            'password': str,
        }
    )
}

config = confuse.LazyConfig('pvecontrol', __name__)

# Pretty output a table from a table of dicts
# We assume all dicts have the same keys and are sorted by key
def _print_tableoutput(table, sortby=None, filter=[]):
  x = PrettyTable()
  x.field_names = table[0].keys()
  [ x.add_row( line.values() ) for line in table ]
  print(x.get_string(sortby=sortby))

def _filter_keys(input, keys):
  # Filter keys from input dict
  output = OrderedDict()
  for key in keys:
      output[key] = input[key]
  return output

def action_nodelist(proxmox, args):
#   # List proxmox nodes in the cluster using proxmoxer api
  nodes = []
  for node in proxmox.nodes.get():
    node = _filter_keys(node, ['node', 'maxcpu', 'status','maxmem','maxdisk'])
    allocated_mem = 0
    for vm in proxmox.nodes(node['node']).qemu.get():
      if vm['status'] == 'running':
        config = proxmox.nodes(node['node']).qemu(vm['vmid']).config.get()
        allocated_mem += config['memory']
    # We convert from MB to Bytes
    node['allocatedmem'] = naturalsize(allocated_mem * 1024 * 1024, binary=True)
    node['maxmem'] = naturalsize(node['maxmem'], binary=True)
    node['maxdisk'] = naturalsize(node['maxdisk'], binary=True)
    nodes.append(node)
  _print_tableoutput(nodes, sortby='node')

def action_vmlist(proxmox, args):
#   # List proxmox nodes in the cluster using proxmoxer api
  vms = []
  for node in proxmox.nodes.get():
    for vm in proxmox.nodes(node['node']).qemu.get():
      vm = _filter_keys(vm, ['vmid', 'status', 'cpus', 'maxdisk', 'maxmem', 'name'])
      vm['node'] = node['node']
      vm['maxmem'] = naturalsize(vm['maxmem'], binary=True)
      vm['maxdisk'] = naturalsize(vm['maxdisk'], binary=True)
      vms.append( vm )
  _print_tableoutput(vms, sortby='vmid')

def _parser():
  # Parser configuration
  parser = argparse.ArgumentParser(description='Proxmox VE control cli.')
  parser.add_argument('-v', '--verbose', action='store_true')
  parser.add_argument('-c', '--cluster', action='store', required=True, help='Proxmox cluster name as defined in configuration' )
  subparsers = parser.add_subparsers(help='sub-command help', dest='action_name')

  # nodelist parser
  parser_nodelist = subparsers.add_parser('nodelist', help='List nodes in the cluster')
  parser_nodelist.set_defaults(func=action_nodelist)
  # vmlist parser
  parser_vmlist = subparsers.add_parser('vmlist', help='List VMs in the cluster')
  parser_vmlist.set_defaults(func=action_vmlist)

  return parser.parse_args()

# Disable urllib3 warnings about invalid certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

args = _parser()
# Start
print("Proxmox cluster: %s" % args.cluster)
# Load configuration file

# FIXME Creation du directory de configuration si non existant
#print('configuration directory is', config.config_dir())
validconfig = config.get(configtemplate)
#pprint.pprint(validconfig)

# FIXME trouver une methode plus clean pour recuperer la configuration du bon cluster
# Peut etre rework la configuration completement avec un dict
clusterconfig = False
for c in validconfig.clusters:
  if c.name == args.cluster:
    clusterconfig = c
if not clusterconfig:
  print('No such cluster %s'%args.cluster)
  sys.exit(1)
#pprint.pprint(clusterconfig)

proxmox = ProxmoxAPI(clusterconfig.host, user=clusterconfig.user, password=clusterconfig.password, verify_ssl=False)

args.func(proxmox, args)
