from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


COLUMNS = ["vmid", "name", "status", "node", "cpus", "maxmem", "maxdisk", "tags"]


class VmStatus(Enum):
    STOPPED = 0
    RUNNING = 1
    PAUSED = 2
    SUSPENDED = 3
    POSTMIGRATE = 4
    PRELAUNCH = 5


@dataclass
class PVEVmData:
    api: object = None
    node: str = field(default="")
    status: Optional["VmStatus"] = None
    vmid: int = field(default=0)
    name: str = field(default="")
    lock: str = field(default="")
    pool: str = field(default="")
    maxcpu: int = field(default=0)
    maxdisk: int = field(default=0)
    maxmem: int = field(default=0)
    uptime: int = field(default=0)
    tags: str = field(default="")
    template: int = field(default=0)


class PVEVm(PVEVmData):
    """Proxmox VE Qemu VM"""

    _api = None
    _config = None

    def __init__(self, api, **kwargs):
        _values = {k: v for k, v in kwargs.items() if hasattr(PVEVmData, k)}
        super().__init__(**_values)
        if isinstance(self.status, str):
            self.status = VmStatus[self.status.upper()]
        self._api = api
        self.tags = set(filter(None, self.tags.split(";")))
        self.cpus = self.maxcpu

    @property
    def config(self):
        if not self._config:
            self._config = self._api.nodes(self.node).qemu(self.vmid).config.get()

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
        output = []
        for k in str_keys:
            output.append(f"{k}: {getattr(self, k)}")
        return ", ".join(output)

    def migrate(self, target, online=False):
        options = {}
        options["node"] = self.node
        options["target"] = target
        check = self._api.nodes(self.node).qemu(self.vmid).migrate.get(**options)
        #    logging.debug("Migration check: %s"%check)
        options["online"] = int(online)
        if len(check["local_disks"]) > 0:
            options["with-local-disks"] = int(True)

        upid = self._api.nodes(self.node).qemu(self.vmid).migrate.post(**options)
        return upid

    def get_backup_jobs(self, proxmox):
        vm_backup_jobs = []
        for backup_job in proxmox.backup_jobs:
            if backup_job.is_selection_matching(self):
                vm_backup_jobs.append(backup_job)
        return vm_backup_jobs

    def get_backups(self, proxmox):
        return [backup for backup in proxmox.backups if backup.vmid == self.vmid]

    def get_last_backup(self, proxmox):
        backups = sorted(self.get_backups(proxmox), key=lambda x: x.ctime)
        return backups[-1] if len(backups) > 0 else None
