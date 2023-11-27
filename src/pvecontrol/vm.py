from enum import Enum

class VmStatus(Enum):
  stopped = 0
  running = 1

class PVEVm:
  """Proxmox VE Qemu VM"""

  _api = None

  def __init__(self, api, node, vmid, status, input = {}):
    self.vmid = vmid
    self.status = VmStatus[status]
    self.node = node
    self._api = api

    self.name = ""
    self.lock = ""
    self.cpus = 0
    self.maxdisk = 0
    self.maxmem = 0
    self.uptime = 0
    self.tags = ""
    for k in input:
      if k == "name":
        self.name = input["name"]
      elif k == "lock":
        self.lock = input["lock"]
      elif k == "cpus":
        self.cpus = input["cpus"]
      elif k == "maxdisk":
        self.maxdisk = input["maxdisk"]
      elif k == "maxmem":
        self.maxmem = input["maxmem"]
      elif k == "uptime":
        self.uptime = input["uptime"]
      elif k == "tags":
        self.tags = input["tags"]
    
    self.config = self._api.nodes(self.node).qemu(vmid).config.get()

  def __str__(self):
    return("vmid: {}, status: {}, name: {}, lock: {}, cpus: {}, maxdisk: {}, maxmem: {}, uptime: {}, tags: {}" 
          .format(self.vmid, self.status, self.name, self.lock, self.cpus, self.maxdisk, self.maxmem, self.uptime, self.tags))
