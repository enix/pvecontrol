from enum import Enum

class VmStatus(Enum):
  stopped = 0
  running = 1

class PVEVm:
  """Proxmox VE Qemu VM"""

  _api = None
  _acceptable_kwargs = (
    "name", "lock", "maxdisk", "maxmem", "uptime", "tags",
  )

  def __init__(self, api, node, vmid, status, **kwargs):
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
    for k in kwargs.keys():
       if k in [self._acceptable_kwargs]:
          self.__setattr__(k, kwargs[k])
    self.config = self._api.nodes(self.node).qemu(vmid).config.get()

  def __str__(self):
    return(
      f"vmid: {self.vmid}, status: {self.vmid}, name: {self.name}, " + \
      f"lock: {self.lock}, cpus: {self.cpus}, maxdisk: {self.maxdisk}, " + \
      f"maxmem: {self.maxmem}, uptime: {self.uptime}, tags: {self.tags}"
    )

  def migrate(self, target, online = False):
    options = {}
    options['node'] = self.node
    options['target'] = target
    check = self._api.nodes(self.node).qemu(self.vmid).migrate.get(**options)
#    logging.debug("Migration check: %s"%check)
    options['online'] = int(online)
    if len(check['local_disks']) > 0:
      options['with-local-disks'] = int(True)

    upid = self._api.nodes(self.node).qemu(self.vmid).migrate.post(**options)
    return upid
