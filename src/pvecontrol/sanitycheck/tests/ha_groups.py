from pvecontrol.sanitycheck.checks import Check, CheckType, CheckMessage, CheckCode


class HaGroups(Check):

  id = "ha_groups"
  type = CheckType.HA
  name = "Check HA groups"

  def run(self):
    for group in self.proxmox.ha()['groups']:
      num_nodes = len(group['nodes'].split(","))
      if num_nodes < 2:
        msg = f"Group {group['group']} contain only {num_nodes} node"
        self.add_messages(CheckMessage(CheckCode.CRIT, msg))

    if not self.messages:
      msg = "HA Group checked"
      self.add_messages(CheckMessage(CheckCode.OK, msg))
