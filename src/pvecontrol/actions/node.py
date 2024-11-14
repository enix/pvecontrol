import logging
import time

from pvecontrol.config import get_config
from pvecontrol.node import NodeStatus
from pvecontrol.vm import VmStatus
from pvecontrol.utils import (
    filter_keys, print_tableoutput, print_task, print_taskstatus
)


def action_nodelist(proxmox, args):
  """List proxmox nodes in the cluster using proxmoxer api"""
  nodes = [ filter_keys(n.__dict__, ['node', 'status', 'allocatedcpu', 'maxcpu', 'mem', 'allocatedmem', 'maxmem']) for n in proxmox.nodes ]
  print_tableoutput(nodes, sortby='node')

def action_nodeevacuate(proxmox, args):
  """Evacuate a node by migrating all it's VM out"""
  validconfig = get_config()

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
      print_task(proxmox, upid, args.follow, args.wait)
    else:
      print("Dry run, skipping migration")
