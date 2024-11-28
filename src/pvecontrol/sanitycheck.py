import re

from enum import Enum

from pvecontrol.cluster import PVECluster
from pvecontrol.storage import StorageShared
from pvecontrol.utils import fonts

class CheckType(Enum):
  HA = 'HIGHT_AVAILABILITY'
  Node = "NODE"

class CheckCode(Enum):
  CRIT = 'CRITICAL'
  WARN = 'WARNING'
  INFO = 'INFO'
  OK = 'OK'

ICONS = {
  CheckCode.CRIT.value: '❌',
  CheckCode.WARN.value: '⚠️',
  CheckCode.INFO.value: 'ℹ️',
  CheckCode.OK.value: '✅',
}

class CheckMessage:
  def __init__(self, code: CheckCode, message):
    self.code = code
    self.message = message

  def display(self, padding_max_size):
    padding = padding_max_size - len(self.message)
    print(f"{self.message}{padding * '.'}{ICONS[self.code.value]}")

  def __len__(self):
    return len(self.message)

class Check:

  def __init__(self, type: CheckType, name: str, messages = None):
    if messages is None:
      messages = []
    self.type = type
    self.name = name
    self.messages = messages

  def add_messages(self, messages):
    if isinstance(messages, CheckMessage):
      self.messages.append(messages)
    elif isinstance(messages, list):
      self.messages += messages

  def set_code(self, code: CheckCode):
    self.code = code

  def display(self, padding_max_size):
    print(f"{fonts.BOLD}{self.name}{fonts.END}\n")
    for msg in self.messages:
      msg.display(padding_max_size)
    print()

class SanityCheck():

    check_methods = (
      "_validate_ha_groups",
      "_validate_ha_vms",
    )

    check_display_order = [
      CheckType.HA,
    ]

    def __init__(self, proxmox: PVECluster):
      self._proxmox = proxmox
      self._ha = self._proxmox.ha()
      self._checks = []

    def run(self):
      for method in SanityCheck.check_methods:
        self._checks.append(getattr(self, method)())

    def _get_longest_message(self):
      size = 0
      for check in self._checks:
        for msg in check.messages:
          if len(msg) > size:
            size = len(msg)
      return size + 1

    def display(self):
      size = self._get_longest_message()
      current_type = None
      for check in self._checks:
        if current_type != check.type:
          current_type = check.type
          dash_size = int((size - (len(check.type.value) + 2))/2)
          print(f"{dash_size*'-'} {check.type.value} {dash_size*'-'}\n")
        check.display(size)

    # Check HA groups
    def _validate_ha_groups(self):
      check = Check(CheckType.HA, "Check HA groups")
      for group in self._ha['groups']:
        num_nodes = len(group['nodes'].split(","))
        if num_nodes < 2:
          msg = f"Group {group['group']} contain only {num_nodes} node"
          check.add_messages(CheckMessage(CheckCode.WARN, msg))

      if check.messages == None:
        msg = "HA Group checked"
        check.add_messages(CheckMessage(CheckCode.OK, msg))
      return check

    # Check disk are shared
    def _validate_ha_vms(self):
      check = Check(CheckType.HA, "Check VMs in a HA group")
      ha_resources = [r for r in self._ha['resources'] if r['type'] in ['vm']]
      ha_vms = []
      for resource in ha_resources:
        id = resource['sid'].split(':')[1]
        if resource['type'] == 'vm':
            ha_vms.append(self._proxmox.get_vm(id))

      regex = r"^(.*):(vm|base)-[0-9]+-(disk|cloudinit).*"
      vms_not_consistent = []
      for vm in ha_vms:
        result = {'name': vm.name, 'node': vm.node, 'disks': []}
        for k, v in vm.config.items():
          if not isinstance(v, str):
            continue
          if regex_result := re.search(regex, v):
            storage = self._proxmox.get_storage(regex_result.group(1))
            if (
                storage != None and
                StorageShared[storage.shared] != StorageShared.shared
            ):
                result['disks'].append(k)
        if result['disks']:
            vms_not_consistent.append(result)

        for vm in vms_not_consistent:
          msg = f"Node '{vm['node']}' has VM '{vm['name']}' with disk(s) '{', '.join(vm['disks'])}' not on shared storage"
          check.add_messages(CheckMessage(CheckCode.WARN, msg))

      if not check.messages:
        msg = "HA VMS checked"
        check.add_messages(CheckMessage(CheckCode.OK, msg))
      return check
