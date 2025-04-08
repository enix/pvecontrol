from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict
from proxmoxer import ProxmoxAPI
from pvecontrol.utils import dict_to_attr


COLUMNS = ["vmid", "name", "status", "node", "cpus", "maxmem", "maxdisk", "tags"]


class VmStatus(Enum):
    STOPPED = 0
    RUNNING = 1
    PAUSED = 2
    SUSPENDED = 3
    POSTMIGRATE = 4
    PRELAUNCH = 5


@dataclass
class PVEVm:
    """Proxmox VE Qemu VM"""

    api: ProxmoxAPI
    node: str
    vmid: int
    status: VmStatus
    kwargs: Dict[str, Any] = field(default_factory=dict)

    name: str = field(init=True, default="")
    lock: str = field(init=True, default="")
    cpus: int = field(init=True, default=0)
    maxdisk: int = field(init=True, default=0)
    maxmem: int = field(init=True, default=0)
    uptime: int = field(init=True, default=0)
    template: int = field(init=True, default=0)
    pool: str = field(init=True, default="")
    tags: str = field(init=True, default="")

    def __post_init__(self):
        dict_to_attr(self, "kwargs")
        self.status = VmStatus[self.status.upper()]
        self.tags = set(self.tags.split(";"))
        self._config = None

    @property
    def config(self):
        if not self._config:
            self._config = self.api.nodes(self.node).qemu(self.vmid).config.get()

        return self._config

    def __str__(self):
        str_keys = [
            "vmid",
            "status",
            "name",
            "lock",
            "cpus",
            "maxdisk",
            "maxmem",
            "uptime",
            "tags",
            "template",
        ]
        output = [f"{k}: {getattr(self, k)}" for k in str_keys]
        return ", ".join(output)

    def migrate(self, target, online=False):
        options = {}
        options["node"] = self.node
        options["target"] = target
        check = self.api.nodes(self.node).qemu(self.vmid).migrate.get(**options)
        #    logging.debug("Migration check: %s"%check)
        options["online"] = int(online)
        if len(check["local_disks"]) > 0:
            options["with-local-disks"] = int(True)

        return self.api.nodes(self.node).qemu(self.vmid).migrate.post(**options)

    def get_backup_jobs(self, proxmox):
        return [job for job in proxmox.backup_jobs if job.is_selection_matching(self)]

    def get_backups(self, proxmox):
        return [backup for backup in proxmox.backups if backup.vmid == self.vmid]

    def get_last_backup(self, proxmox):
        backups = sorted(self.get_backups(proxmox), key=lambda x: x.ctime)
        return backups[-1] if len(backups) > 0 else None
