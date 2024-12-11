import re

from pvecontrol.storage import StorageShared
from pvecontrol.sanitycheck.checks import Check, CheckType, CheckMessage, CheckCode


class HaVms(Check):

  id = "ha_vms"
  type = CheckType.HA
  name = "Check VMs in a HA group"

  def run(self):
    ha_resources = [r for r in self.proxmox.ha['resources'] if r['type'] in ['vm']]
    ha_vms = []
    for resource in ha_resources:
      id = resource['sid'].split(':')[1] # "sid = vm:100"
      if resource['type'] == 'vm':
        ha_vms.append(self.proxmox.get_vm(id))

    self.add_messages(self._check_disk_ha_consistency(ha_vms))
    self.add_messages(self._check_cpu_ha_consistency(ha_vms))

    if not self.messages:
      msg = "HA VMS checked"
      self.add_messages(CheckMessage(CheckCode.OK, msg))

  def _check_disk_ha_consistency(self, ha_vms):
    messages = []
    # Value are quite hard to find from ressources keys if it's a disk
    regex = r"^(.*):(vm|base)-[0-9]+-(disk|cloudinit).*"
    vms_not_consistent = []
    for vm in ha_vms:
      result = {'name': vm.name, 'node': vm.node, 'disks': []}
      for k, v in vm.config.items():
        if not isinstance(v, str):
          continue
        if regex_result := re.search(regex, v):
          storage = self.proxmox.get_storage(regex_result.group(1))
          if (
              storage != None and
              StorageShared[storage.shared] != StorageShared.shared
          ):
              result['disks'].append(k)
      if result['disks']:
          vms_not_consistent.append(result)

    for vm in vms_not_consistent:
      msg = f"Node '{vm['node']}' has VM '{vm['name']}' with disk(s) '{', '.join(vm['disks'])}' not on shared storage"
      messages.append(CheckMessage(CheckCode.CRIT, msg))

    return messages

  def _check_cpu_ha_consistency(self, ha_vms):
    messages = []
    for vm in ha_vms:
      if vm.config.get('cpu', '') == 'host':
        msg = f"Node '{vm.node}' has VM '{vm.name}' with cpu type host"
        messages.append(CheckMessage(CheckCode.WARN, msg))
      else:
        msg = f"Node '{vm.node}' has VM '{vm.name}' with cpu type {vm.config.get('cpu', 'Default')}"
        messages.append(CheckMessage(CheckCode.OK, msg))
    return messages
