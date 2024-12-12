from .nodes import Nodes
from .ha_groups import HaGroups
from .ha_vms import HaVms


DEFAULT_CHECKS = {Nodes.id: Nodes, HaGroups.id: HaGroups, HaVms.id: HaVms}

DEFAULT_CHECK_IDS = DEFAULT_CHECKS.keys()
