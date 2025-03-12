from .nodes import Nodes
from .ha_groups import HaGroups
from .ha_vms import HaVms
from .vm import VmsStartOnBoot, DiskUnused
from .vm_backups import VmBackups

DEFAULT_CHECKS = {
    Nodes.id: Nodes,
    HaGroups.id: HaGroups,
    HaVms.id: HaVms,
    VmsStartOnBoot.id: VmsStartOnBoot,
    VmBackups.id: VmBackups,
    DiskUnused.id: DiskUnused,
}

DEFAULT_CHECK_IDS = DEFAULT_CHECKS.keys()
