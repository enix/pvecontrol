import logging

from pvecontrol.config import get_config
from pvecontrol.utils import _filter_keys, _print_tableoutput


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

def action_sanitycheck(proxmox, args):
  """Check status of proxmox Cluster"""
  # check cpu allocation factor
  validconfig = get_config()

  for node in proxmox.nodes:
    if (node.maxcpu * validconfig.node.cpufactor) <= node.allocatedcpu:
      print("Node %s is in cpu overcommit status: %s allocated but %s available"%(node.node, node.allocatedcpu, node.maxcpu))
    if (node.allocatedmem + validconfig.node.memoryminimum) >= node.maxmem:
      print("Node %s is in mem overcommit status: %s allocated but %s available"%(node.node, node.allocatedmem, node.maxmem))
  # More checks to implement
  # VM is started but 'startonboot' not set
  # VM is running in cpu = host
  # VM is running in cpu = qemu64
