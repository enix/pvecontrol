#!/usr/bin/env python

import os
import time
import sys
import argparse
import confuse
import urllib3
import logging
from prettytable import PrettyTable
from collections import OrderedDict
from humanize import naturalsize

from pvecontrol.node import PVENode
from pvecontrol.node import NodeStatus
from pvecontrol.vm import PVEVm
from pvecontrol.vm import VmStatus
from pvecontrol.task import PVETask
from pvecontrol.cluster import PVECluster


configtemplate = {
    'clusters': confuse.Sequence(
        {
            'name': str,
            'host': str,
            'user': str,
            'password': str,
        }
    ),
    'node': {
        'cpufactor': float,
        'memoryminimum': int
      }
}

config = confuse.LazyConfig('pvecontrol', __name__)

# Pretty output a table from a table of dicts
# We assume all dicts have the same keys and are sorted by key
def _print_tableoutput(table, sortby=None, filter=[]):
  x = PrettyTable()
  x.align = 'l'
  x.field_names = table[0].keys()
  for line in table:
    for key in ['mem', 'allocatedmem', 'maxmem', 'disk', 'allocateddisk', 'maxdisk'] :
      if key in line:
        line[key] = naturalsize(line[key], binary=True)
    x.add_row( line.values() )
  print(x.get_string(sortby=sortby))

def _filter_keys(input, keys):
  # Filter keys from input dict
  output = OrderedDict()
  for key in keys:
      output[key] = input[key]
  return output

def _get_vm(proxmox, vmid):
  for vm in proxmox.vms():
    logging.debug("_get_vm: %s"%vm)
    if vm.vmid == vmid:
      return vm
  return None

def action_test(proxmox, args):
  """Hidden optional test action"""
  print(proxmox)

def action_clusterstatus(proxmox, args):
  logging.debug(proxmox.status)
  logging.debug(proxmox.resources)
  status = _filter_keys(proxmox.status[0], ['name', 'nodes', 'quorate'])
  nodes = [ _filter_keys(n, ['name', 'ip', 'online']) for n in proxmox.status[1:] ]
# FIXME get cluster maxmem
# FIXME get cluster maxcpu
# FIXME get cluster allocatedmem
# FIXME get cluster allocatedcpu
  _print_tableoutput([status])
  _print_tableoutput(nodes)

def action_nodelist(proxmox, args):
  """List proxmox nodes in the cluster using proxmoxer api"""
  nodes = [ _filter_keys(n.__dict__, ['node', 'status', 'allocatedcpu', 'maxcpu', 'mem', 'allocatedmem', 'maxmem']) for n in proxmox.nodes ]
  _print_tableoutput(nodes, sortby='node')

def action_nodeevacuate(proxmox, args):
  """Evacuate a node by migrating all it's VM out"""
  # check node exists
  srcnode = proxmox.find_node(args.node)
  logging.debug(srcnode)
  if not srcnode:
    print("Node %s does not exist"%args.node)
    return
  # check node is online
  if srcnode.status != NodeStatus.online:
    print("Node %s is not online"%args.node)
    return

  targets = []
  # compute targets migration possible
  if args.target:
    for t in list(set(args.target)):
      if t == srcnode.node:
        print("Target node %s is the same as source node, skipping"%t)
        continue
      tg = proxmox.find_node(t)
      if not tg:
        print("Target node %s does not exist, skipping"%t)
        continue
      if tg.status != NodeStatus.online:
        print("Target node %s is not online, skipping"%t)
        continue
      targets.append(tg)
  else:
    targets = [n for n in proxmox.nodes if n.status == NodeStatus.online and n.node != srcnode.node]
  if len(targets) == 0:
    print("No target node available")
    return
  logging.debug("Migration targets: %s"%([t.node for t in targets]))

  plan = []
  for vm in srcnode.vms:
    logging.debug("Selecting node for VM: %i, maxmem: %i, cpus: %i"%(vm.vmid, vm.maxmem, vm.cpus))
    if vm.status != VmStatus.running and not args.no_skip_stopped:
      logging.debug("VM %i is not running, skipping"%(vm.vmid))
      continue
    # check ressources
    for target in targets: 
      logging.debug("Test target: %s, allocatedmem: %i, allocatedcpu: %i"%(target.node, target.allocatedmem, target.allocatedcpu))
      if (vm.maxmem + target.allocatedmem) > (target.maxmem - validconfig.node.memoryminimum):
        logging.debug("Discard target: %s, will overcommit ram"%(target.node))
      elif (vm.cpus + target.allocatedcpu) > (target.maxcpu *  validconfig.node.cpufactor):
        logging.debug("Discard target: %s, will overcommit cpu"%(target.node))
      else:
        plan.append({"vmid": vm.vmid, "vm": vm, "node": args.node, "target": target})
        target.allocatedmem += vm.maxmem
        target.allocatedcpu += vm.cpus
        logging.debug("Selected target %s: new allocatedmem %i, new allocatedcpu %i"%(target.node, target.allocatedmem, target.allocatedcpu))
        break
    else:
      print("No target found for VM %s"%vm.vmid)
      

  logging.debug(plan)
  # validate input
  if len(plan) == 0:
    print("No VM to migrate")
    return
  for p in plan:
    print("Migrating VM %s (%s) from %s to %s"%(p['vmid'], p['vm'].name, p['node'], p['target'].node))
  confirmation = input('Confirm (yes):')
  logging.debug("Confirmation input: %s"%confirmation)
  if confirmation.lower() != "yes":
    print("Aborting")
    return
  # run migrations

  for p in plan:
    logging.debug("Migrating VM %s from %s to %s"%(p['vmid'], p['node'], p['target'].node))
    print("Migrate VM: %i / %s from %s to %s"%(p['vmid'], p['vm'].name, p['node'], p['target'].node))
    if not args.dry_run:
      upid = p['vm'].migrate(p['target'].node, args.online)
      logging.debug("Migration UPID: %s"%upid)
      proxmox.refresh()
      task = proxmox.find_task(upid)
      if args.follow:
        _print_task(proxmox, upid, args.follow)
      else:
        _print_taskstatus(task)
      # wait for task completion
      while task.running():
        logging.debug("Task status: %s", task.runningstatus)
        task.refresh()
        time.sleep(1)
      _print_taskstatus(task)

    else:
      print("Dry run, skipping migration")


def action_vmlist(proxmox, args):
  """List VMs in the Proxmox Cluster"""
  vms = [ _filter_keys(n.__dict__, ['vmid', 'name', 'status', 'node', 'cpus', 'maxmem', 'maxdisk']) for n in proxmox.vms() ]
  _print_tableoutput(vms, sortby='vmid')


def action_vmmigrate(proxmox, args):
  logging.debug("ARGS: %s"%args)
  # Migrate a vm to a node
  vmid = int(args.vmid)
  target = str(args.target)

  # Check that vmid exists
  vm = _get_vm(proxmox, vmid)
  logging.debug("Source vm: %s"%vm)
  if not vm:
    print("Source vm not found")
    sys.exit(1)
  # Get source node
  node = proxmox.find_node(vm.node)
  if not node:
    print("Source node does not exists")
    sys.exit(1)
  logging.debug("Source node: %s"%node)

  # Check target node exists
  target = proxmox.find_node(target)
  if not target:
    print("Target node does not exists")
    sys.exit(1)
  # Check target node a les ressources
  # FIXME

  # Check que la migration est possible
  check = proxmox._api.nodes(node.node).qemu(vmid).migrate.get(node= node.node, target= target.node)
  logging.debug("Migration check: %s"%check)
  options = {}
  options['node'] = node.node
  options['target'] = target.node
  options['online'] = int(args.online)
  if len(check['local_disks']) > 0:
    options['with-local-disks'] = int(True)

  if not args.dry_run:
    # Lancer tache de migration
    upid = proxmox._api.nodes(node.node).qemu(vmid).migrate.post(**options)
    # Suivre la task cree
    proxmox.refresh()
    task = proxmox.find_task(upid)
    if args.follow:
      _print_task(proxmox, upid, args.follow)
    else:
      _print_taskstatus(task)
    # wait for task completion
    while task.running():
      logging.debug("Task status: %s", task.runningstatus)
      task.refresh()
      time.sleep(1)
    _print_taskstatus(task)

  else:
    print("Dry run, skipping migration")

def action_tasklist(proxmox, args):
  tasks = [ _filter_keys(t.__dict__, ['upid', 'exitstatus', 'node', 'type', 'starttime', 'endtime', 'runningstatus', 'description']) for t in proxmox.tasks ]
  _print_tableoutput(tasks, sortby='starttime')

def _print_taskstatus(task):
  output = [ _filter_keys(task.__dict__, ['upid', 'exitstatus', 'node', 'runningstatus', 'type', 'user', 'starttime']) ]
  _print_tableoutput(output)

def action_taskget(proxmox, args):
  _print_task(proxmox, args.upid, args.follow)

def _print_task(proxmox, upid, follow = False):
  task = proxmox.find_task(upid)
  logging.debug("Task: %s", task)
  _print_taskstatus(task)
  log = task.log(limit=0)
  logging.debug("Task Log: %s", log)
  if task.running() and follow:
    lastline = 0
    print("log output, follow mode")
    while task.running():
      task.refresh()
#      logging.debug("Task status: %s", status)
      log = task.log(limit=0, start=lastline)
      logging.debug("Task Log: %s", log)
      for line in log:
        print("%s"%line['t'])
        if line['n'] > lastline:
          lastline = line['n']
      time.sleep(1)
    _print_taskstatus(task)
  else:
    _print_tableoutput([{"log output": task.decode_log()}])

def action_sanitycheck(proxmox, args):
  """Check status of proxmox Cluster"""
  # check cpu allocation factor
  for node in proxmox.nodes:
    if (node.maxcpu * validconfig.node.cpufactor) <= node.allocatedcpu:
      print("Node %s is in cpu overcommit status: %s allocated but %s available"%(node.node, node.allocatedcpu, node.maxcpu))
    if (node.allocatedmem + validconfig.node.memoryminimum) >= node.maxmem:
      print("Node %s is in mem overcommit status: %s allocated but %s available"%(node.node, node.allocatedmem, node.maxmem))
  # More checks to implement
  # VM is started but 'startonboot' not set
  # VM is running in cpu = host
  # VM is running in cpu = qemu64


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
  parser_clusterstatus.set_defaults(func=action_clusterstatus)
  
  # nodelist parser
  parser_nodelist = subparsers.add_parser('nodelist', help='List nodes in the cluster')
  parser_nodelist.set_defaults(func=action_nodelist)
  # nodeevacuate parser
  parser_nodeevacuate = subparsers.add_parser('nodeevacuate', help='Evacuate an host by migrating all VMs')
  parser_nodeevacuate.add_argument('--node', action='store', required=True, help="Node to evacuate")
  parser_nodeevacuate.add_argument('--target', action='append', required=False, help="Destination Proxmox VE node, you can specify multiple target options")
  parser_nodeevacuate.add_argument('-f', '--follow', action='store_true', help="Follow task log output")
  parser_nodeevacuate.add_argument('--online', action='store_true', help="Online migrate the VM, default True", default=True)
  parser_nodeevacuate.add_argument('--no-skip-stopped', action='store_true', help="Don't skip VMs that are stopped")
  parser_nodeevacuate.add_argument('--dry-run', action='store_true', help="Dry run, do not execute migration")
  parser_nodeevacuate.set_defaults(func=action_nodeevacuate)

  # vmlist parser
  parser_vmlist = subparsers.add_parser('vmlist', help='List VMs in the cluster')
  parser_vmlist.set_defaults(func=action_vmlist)
  # vmmigrate parser
  parser_vmmigrate = subparsers.add_parser('vmmigrate', help='Migrate VMs in the cluster')
  parser_vmmigrate.add_argument('--vmid', action='store', required=True, type=int, help="VM to migrate")
  parser_vmmigrate.add_argument('--target', action='store', required=True, help="Destination Proxmox VE node")
  parser_vmmigrate.add_argument('--online', action='store_true', help="Online migrate the VM, default True", default=True)
  parser_vmmigrate.add_argument('-f', '--follow', action='store_true', help="Follow task log output")
  parser_vmmigrate.add_argument('--dry-run', action='store_true', help="Dry run, do not execute migration")
  parser_vmmigrate.set_defaults(func=action_vmmigrate)

  # tasklist parser
  parser_tasklist = subparsers.add_parser('tasklist', help='List tasks')
  parser_tasklist.set_defaults(func=action_tasklist)
  # taskget parser
  parser_taskget = subparsers.add_parser('taskget', help='Get task detail')
  parser_taskget.add_argument('--upid', action='store', required=True, help="Proxmox tasks UPID to get informations")
  parser_taskget.add_argument('-f', '--follow', action='store_true', help="Follow task log output")
  parser_taskget.set_defaults(func=action_taskget)

  # sanitycheck parser
  parser_sanitycheck = subparsers.add_parser('sanitycheck', help='Run Sanity checks on the cluster')
  parser_sanitycheck.set_defaults(func=action_sanitycheck)


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

  # Load configuration file
  # FIXME Creation du directory de configuration si non existant
  logging.debug('configuration directory is %s'%config.config_dir())
  global validconfig
  validconfig = config.get(configtemplate)
  logging.debug('configuration is %s'%validconfig)

  # FIXME trouver une methode plus clean pour recuperer la configuration du bon cluster
  # Peut etre rework la configuration completement avec un dict
  clusterconfig = False
  for c in validconfig.clusters:
    if c.name == args.cluster:
      clusterconfig = c
  if not clusterconfig:
    print('No such cluster %s'%args.cluster)
    sys.exit(1)
  logging.debug('clusterconfig is %s'%clusterconfig)

  proxmoxcluster = PVECluster(clusterconfig.name, clusterconfig.host, user=clusterconfig.user, password=clusterconfig.password, verify_ssl=False)

  args.func(proxmoxcluster, args)


if __name__ == '__main__':
    sys.exit(main())
