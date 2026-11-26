from proxmoxer.core import ResourceException

from pvecontrol.sanitycheck.checks import Check, CheckType, CheckMessage, CheckCode
from pvecontrol.utils import parse_pve_version


class HaRules(Check):

    id = "ha_rules"
    type = CheckType.HA
    name = "Check HA rules"

    def run(self):
        # HA rules replace the HA groups since Proxmox VE 9.0
        if parse_pve_version(self.proxmox.version["release"]) < (9, 0):
            self.add_messages(CheckMessage(CheckCode.OK, "No HA rules before Proxmox VE 9.0"))
            return
        try:
            rules = self.proxmox.ha_rules
        except ResourceException as error:
            self.add_messages(CheckMessage(CheckCode.WARN, f"HA rules can't be read: {error}"))
            return

        for rule in sorted(rules, key=lambda rule: rule.rule):
            if rule.disable:
                msg = f"HA rule '{rule.rule}' is disabled"
                self.add_messages(CheckMessage(CheckCode.WARN, msg))
            elif rule.errors:
                # The HA manager drops it: an anti-affinity, for instance, is not enforced anymore
                msg = f"HA rule '{rule.rule}' is ignored by the HA manager: {rule.errors}"
                self.add_messages(CheckMessage(CheckCode.CRIT, msg))

        if not self.messages:
            self.add_messages(CheckMessage(CheckCode.OK, "HA rules checked"))
