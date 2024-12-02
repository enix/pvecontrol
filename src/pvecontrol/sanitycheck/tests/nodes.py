from pvecontrol.sanitycheck.checks import Check, CheckType, CheckMessage, CheckCode

def _check_cpu_overcommit(maxcpu, cpufactor, allocated_cpu):
  return (maxcpu *  cpufactor) <= allocated_cpu

def _check_mem_overcommit(max_mem, min_mem, allocated_mem):
  return (allocated_mem +  min_mem) >= max_mem

# Check nodes capacity
def get_checks(sanitity):
  node_config = sanitity._proxmox.config['node']
  check = Check(CheckType.Node, "Check Node capacity")
  for node in sanitity._proxmox.nodes:
    if _check_cpu_overcommit(node.maxcpu, node_config['cpufactor'], node.allocatedcpu):
      msg = "Node %s is in cpu overcommit status: %s allocated but %s available"%(node.node, node.allocatedcpu, node.maxcpu)
      check.add_messages(CheckMessage(CheckCode.CRIT, msg))
    else:
      msg = f"Node '{node.node}' isn't in cpu overcommit"
      check.add_messages(CheckMessage(CheckCode.OK, msg))

  for node in sanitity._proxmox.nodes:
    if _check_mem_overcommit(node.allocatedmem, node_config['memoryminimum'], node.maxmem):
      msg = f"Node '{node.node}' is in mem overcommit status: {node.allocatedmem} allocated but {node.maxmem} available"
      check.add_messages(CheckMessage(CheckCode.CRIT, msg))
    else:
      msg = f"Node '{node.node}' isn't in cpu overcommit"
      check.add_messages(CheckMessage(CheckCode.OK, msg))
  return [check]
