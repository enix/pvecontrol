#!/usr/bin/env python

import os
import sys
import argparse
import confuse
import pprint
from proxmoxer import ProxmoxAPI


configtemplate = {
    'clusters': confuse.Sequence(
        {
            'name': str,
            'url': str,
            'user': str,
            'password': str,
        }
    )
}

config = confuse.Configuration('pvecontrol', __name__)

def _nodelist(args):
#   # List proxmox nodes in the cluster using proxmoxer api
  print("Listing nodes in the cluster: %s"%args)

def _vmlist(args):
#   # List proxmox nodes in the cluster using proxmoxer api
  print("Listing vms in the cluster: %s"%args)

def _parser():
  # Parser configuration
  parser = argparse.ArgumentParser(description='Proxmox VE control cli.')
  parser.add_argument('-v', '--verbose', action='store_true')
  parser.add_argument('-c', '--cluster', action='store', required=True, help='Proxmox cluster name as defined in configuration' )
  subparsers = parser.add_subparsers(help='sub-command help', dest='action_name')

  # nodelist parser
  parser_nodelist = subparsers.add_parser('nodelist', help='List nodes in the cluster')
  parser_nodelist.set_defaults(func=_nodelist)
  # vmlist parser
  parser_vmlist = subparsers.add_parser('vmlist', help='List VMs in the cluster')
  parser_vmlist.set_defaults(func=_vmlist)

  return parser.parse_args()

args = _parser()
# Start
print("Proxmox cluster: %s" % args.cluster)
# Load configuration file

print('configuration directory is', config.config_dir())
valid = config.get(configtemplate)
pprint.pprint(valid)

args.func(args)
