from proxmoxer.core import ResourceException

from pvecontrol.models.node import NodeHaState, parse_node_ha_states
from pvecontrol.sanitycheck.checks import Check, CheckType, CheckMessage, CheckCode

# A node the HA manager has lost: its resources are not running, or are about to be fenced
CRITICAL_STATES = (NodeHaState.UNKNOWN, NodeHaState.FENCE)


class HaNodes(Check):

    id = "ha_nodes"
    type = CheckType.HA
    name = "Check nodes in the HA manager"

    def run(self):
        try:
            status = self.proxmox.ha_manager_status
        except ResourceException as error:
            msg = f"HA manager status can't be read: {error}"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))
            return

        disarm = (status.get("manager_status") or {}).get("disarm")
        if disarm:
            state = disarm.get("state", "disarmed")
            msg = f"HA is {state}, resources are in {disarm.get('mode')} mode"
            # While disarming, some nodes may still hold their watchdog
            if state == "disarmed":
                msg += ", no node is fenced"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))

        for node, state in sorted(parse_node_ha_states(status).items()):
            if state in CRITICAL_STATES:
                msg = f"Node '{node}' is in HA state {state}"
                self.add_messages(CheckMessage(CheckCode.CRIT, msg))
            elif state == NodeHaState.MAINTENANCE_REQUESTED:
                msg = f"Node '{node}' has the HA maintenance mode requested"
                self.add_messages(CheckMessage(CheckCode.WARN, msg))
            elif state == NodeHaState.MAINTENANCE:
                msg = f"Node '{node}' is in HA maintenance mode"
                self.add_messages(CheckMessage(CheckCode.WARN, msg))
            elif state == NodeHaState.GONE:
                msg = f"Node '{node}' is gone from the cluster but still known to the HA manager"
                self.add_messages(CheckMessage(CheckCode.WARN, msg))

        if not self.messages:
            msg = "HA nodes checked"
            self.add_messages(CheckMessage(CheckCode.OK, msg))
