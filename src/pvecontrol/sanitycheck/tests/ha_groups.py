from pvecontrol.sanitycheck.checks import Check, CheckType, CheckMessage, CheckCode


class HaGroups(Check):

    id = "ha_groups"
    type = CheckType.HA
    name = "Check HA groups"

    def run(self):
        for group in self.proxmox.ha["groups"]:
            num_nodes = len(group["nodes"].split(","))
            if num_nodes < 2:
                group_name = group.get("group") or group.get("rule", "")
                msg = f"Group {group_name} contain only {num_nodes} node"
                self.add_messages(CheckMessage(CheckCode.CRIT, msg))

        if not self.messages:
            msg = "HA Group checked"
            self.add_messages(CheckMessage(CheckCode.OK, msg))
