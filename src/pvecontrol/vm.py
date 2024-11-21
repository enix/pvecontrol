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

    self.name = input.get("name", "")
    self.lock = input.get("lock", "")
    self.cpus = input.get("cpus", 0)
    self.maxdisk = input.get("maxdisk", 0)
    self.maxmem = input.get("maxmem", 0)
    self.uptime = input.get("uptime", 0)
    self.tags = input.get("tags", "")
    self.template = input.get("template", 0)

    self.config = self._api.nodes(self.node).qemu(vmid).config.get()

  def __str__(self):
    return("vmid: {}, status: {}, name: {}, lock: {}, cpus: {}, maxdisk: {}, maxmem: {}, uptime: {}, tags: {}, template: {}"
          .format(self.vmid, self.status, self.name, self.lock, self.cpus, self.maxdisk, self.maxmem, self.uptime, self.tags, self.template))

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
