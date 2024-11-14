#!/usr/bin/env python

import sys
import argparse
import confuse
import urllib3
import logging

from pvecontrol.cluster import PVECluster
from pvecontrol.config import set_config
from pvecontrol.actions import cluster, node, vm, task

def action_test(proxmox, args):
  """Hidden optional test action"""
  print(proxmox)

def _parser():
## FIXME
## Add version in help output

  # Parser configuration
  parser = argparse.ArgumentParser(description='Proxmox VE control cli.', epilog="Made with love by Enix.io")
  parser.add_argument('-v', '--verbose', action='store_true')
  parser.add_argument('--debug', action='store_true')
  parser.add_argument('-c', '--cluster', action='store', required=True, help='Proxmox cluster name as defined in configuration' )
  subparsers = parser.add_subparsers(required=True)

  # clusterstatus parser
  parser_clusterstatus = subparsers.add_parser('clusterstatus', help='Show cluster status')
  parser_clusterstatus.set_defaults(func=cluster.action_clusterstatus)

  # nodelist parser
  parser_nodelist = subparsers.add_parser('nodelist', help='List nodes in the cluster')
  parser_nodelist.set_defaults(func=node.action_nodelist)
  # nodeevacuate parser
  parser_nodeevacuate = subparsers.add_parser('nodeevacuate', help='Evacuate an host by migrating all VMs')
  parser_nodeevacuate.add_argument('--node', action='store', required=True, help="Node to evacuate")
  parser_nodeevacuate.add_argument('--target', action='append', required=False, help="Destination Proxmox VE node, you can specify multiple target options")
  parser_nodeevacuate.add_argument('-f', '--follow', action='store_true', help="Follow task log output")
  parser_nodeevacuate.add_argument('--online', action='store_true', help="Online migrate the VM, default True", default=True)
  parser_nodeevacuate.add_argument('--no-skip-stopped', action='store_true', help="Don't skip VMs that are stopped")
  parser_nodeevacuate.add_argument('--dry-run', action='store_true', help="Dry run, do not execute migration")
  parser_nodeevacuate.set_defaults(func=node.action_nodeevacuate)

  # vmlist parser
  parser_vmlist = subparsers.add_parser('vmlist', help='List VMs in the cluster')
  parser_vmlist.set_defaults(func=vm.action_vmlist)
  # vmmigrate parser
  parser_vmmigrate = subparsers.add_parser('vmmigrate', help='Migrate VMs in the cluster')
  parser_vmmigrate.add_argument('--vmid', action='store', required=True, type=int, help="VM to migrate")
  parser_vmmigrate.add_argument('--target', action='store', required=True, help="Destination Proxmox VE node")
  parser_vmmigrate.add_argument('--online', action='store_true', help="Online migrate the VM, default True", default=True)
  parser_vmmigrate.add_argument('-f', '--follow', action='store_true', help="Follow task log output")
  parser_vmmigrate.add_argument('-w', '--wait', action='store_true', help="Wait task end")
  parser_vmmigrate.add_argument('--dry-run', action='store_true', help="Dry run, do not execute migration")
  parser_vmmigrate.set_defaults(func=vm.action_vmmigrate)

  # tasklist parser
  parser_tasklist = subparsers.add_parser('tasklist', help='List tasks')
  parser_tasklist.set_defaults(func=task.action_tasklist)
  # taskget parser
  parser_taskget = subparsers.add_parser('taskget', help='Get task detail')
  parser_taskget.add_argument('--upid', action='store', required=True, help="Proxmox tasks UPID to get informations")
  parser_taskget.add_argument('-f', '--follow', action='store_true', help="Follow task log output")
  parser_taskget.add_argument('-w', '--wait', action='store_true', help="Wait task end")
  parser_taskget.set_defaults(func=task.action_taskget)

  # sanitycheck parser
  parser_sanitycheck = subparsers.add_parser('sanitycheck', help='Run Sanity checks on the cluster')
  parser_sanitycheck.set_defaults(func=cluster.action_sanitycheck)


  # _test parser, hidden from help
  parser_test = subparsers.add_parser('_test')
  parser_test.set_defaults(func=action_test)

  return parser.parse_args()


def main():
  # Disable urllib3 warnings about invalid certs
  urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

  # get cli arguments
  args = _parser()

  # configure logging
  logging.basicConfig(encoding='utf-8', level=logging.DEBUG if args.debug else logging.INFO)
  logging.debug("Arguments: %s"%args)
  logging.info("Proxmox cluster: %s" % args.cluster)

  clusterconfig = set_config(args.cluster)

  proxmoxcluster = PVECluster(clusterconfig.name, clusterconfig.host, user=clusterconfig.user, password=clusterconfig.password, verify_ssl=False)

  args.func(proxmoxcluster, args)


if __name__ == '__main__':
    sys.exit(main())
