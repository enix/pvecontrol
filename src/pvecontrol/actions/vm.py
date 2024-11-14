import logging
import sys
import time

from pvecontrol.utils import (
    print_task, print_taskstatus, print_tableoutput, filter_keys
)


def _get_vm(proxmox, vmid):
  for vm in proxmox.vms():
    logging.debug("_get_vm: %s"%vm)
    if vm.vmid == vmid:
      return vm
  return None

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
    print_task(proxmox, upid, args.follow, args.wait)
  else:
    print("Dry run, skipping migration")

def action_vmlist(proxmox, args):
  """List VMs in the Proxmox Cluster"""
  vms = [ filter_keys(n.__dict__, ['vmid', 'name', 'status', 'node', 'cpus', 'maxmem', 'maxdisk']) for n in proxmox.vms() ]
  print_tableoutput(vms, sortby='vmid')
