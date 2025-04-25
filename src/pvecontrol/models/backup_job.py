from dataclasses import dataclass, field
from typing import Optional

from pvecontrol.models.storage import StorageShared


@dataclass
class PVEBackupJobData:
    all: int = field(default=0)
    compress: object = None
    enabled: object = None
    exclude: str = field(default="")
    fleecing: object = None
    mode: str = field(default="")
    next_run: int = field(default=0)
    node: str = field(default="")
    notes_template: str = field(default="")
    pool: str = field(default="")
    prune_backups: object = (None,)
    schedule: str = field(default="")
    storage: Optional["StorageShared"] = None
    type: str = field(default="")
    vmid: str = (field(default=""),)


class PVEBackupJob(PVEBackupJobData):
    """Proxmox VE Backup Job"""

    def __init__(self, backup_id, **kwargs):
        self.id = backup_id
        _values = {k: v for k, v in kwargs.items() if hasattr(PVEBackupJobData, k)}
        super().__init__(**_values)

        self.all = self.all == 1
        if isinstance(self.vmid, str):
            self.vmid = list(self.vmid.split(","))
        if isinstance(self.exclude, str):
            self.exclude = self.exclude.split(",")

    def __str__(self):
        return "\n".join([f"{k.capitalize()}: {v}" for k, v in self.__dict__.items()])

    def is_selection_matching(self, vm):
        if self.node is not None and self.node != vm.node:
            return False
        if self.pool is not None:
            return self.pool == vm.pool
        if self.all:
            return str(vm.vmid) not in self.exclude
        return str(vm.vmid) in self.vmid
