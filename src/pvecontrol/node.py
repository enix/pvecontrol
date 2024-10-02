from enum import Enum

from pvecontrol.vm import PVEVm
from pvecontrol.vm import VmStatus

class NodeStatus(Enum):
  unknown = 0
  online = 1
  offline = 2

class PVENode:
  """A proxmox VE Node"""
  _api = None
 
  def __init__(self, api, node, status, input = {}):
    self.node = node
    self.status = NodeStatus[status]
    self._api = api
    self.cpu = 0
    self.allocatedcpu = 0
    self.maxcpu = 0
    self.mem = 0
    self.allocatedmem = 0
    self.maxmem = 0
    self.disk = 0
    self.maxdisk = 0
    for k in input:
      if k == "cpu":
        self.cpu = input[k]
      elif k == "maxcpu":
        self.maxcpu = input[k]
      elif k == "mem":
        self.mem = input[k]
      elif k == "maxmem":
        self.maxmem = input[k]
      elif k == "disk":
        self.disk = input[k]
      elif k == "maxdisk":
        self.maxdisk = input[k]
    self._init_vms()
    self._init_allocatedmem()
    self._init_allocatedcpu()

  def __str__(self):
    output = "Node: " + self.node + "\n"
    output += "Status: " + str(self.status) + "\n"
    output += "CPU: " + str(self.cpu) + "/" + str(self.allocatedcpu) + "/" + str(self.maxcpu) + "\n"
    output += "Mem: " + str(self.mem) + "/" + str(self.allocatedmem) + "/" + str(self.maxmem) + "\n"
    output += "Disk: " + str(self.disk) + "/" + str(self.maxdisk) + "\n"
    output += "VMs: \n"
    for vm in self.vms:
      output += " - " + str(vm) + "\n"
    return output

  def _init_vms(self):
    self.vms = []
    if self.status == NodeStatus.online:
      self.vms = [ PVEVm(self._api, self.node, vm["vmid"], vm["status"], vm) for vm in  self._api.nodes(self.node).qemu.get() ]

  def _init_allocatedmem(self):
    """Compute the amount of memory allocated to running VMs"""
    self.allocatedmem = 0
    for vm in self.vms:
      if vm.status != VmStatus.running:
        continue
      # This is in MB in configuration
      self.allocatedmem += int(vm.config['memory']) * 1024 * 1024

  def _init_allocatedcpu(self):
    """Compute the amount of cpu allocated to running VMs"""
    self.allocatedcpu = 0
    for vm in self.vms:
      if vm.status!= VmStatus.running:
        continue
      if "sockets" in vm.config:
        self.allocatedcpu += vm.config['sockets'] * vm.config['cores']
      else:
        self.allocatedcpu += vm.config['cores']

  # def __contains__(self, item):
  #   """Check if a VM is running on this node"""
  #   for vm in self.vms:
  #     if vm.vmid == item:
  #       return True
  #   return False
