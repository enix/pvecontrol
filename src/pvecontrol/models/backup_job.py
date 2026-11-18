from dataclasses import dataclass, field
from typing import List, Optional

from pvecontrol.models import api_kwargs, format_fields


@dataclass(eq=False)
class PVEBackupJobData:
    id: str = field(default="")
    all: int = field(default=0)
    compress: Optional[str] = None
    enabled: Optional[int] = None
    exclude: str = field(default="")
    fleecing: Optional[dict] = None
    mode: Optional[str] = None
    next_run: Optional[int] = None
    node: Optional[str] = None
    notes_template: Optional[str] = None
    pool: Optional[str] = None
    prune_backups: Optional[dict] = None
    schedule: Optional[str] = None
    storage: Optional[str] = None
    type: Optional[str] = None
    vmid: str = field(default="")


class PVEBackupJob(PVEBackupJobData):
    """Proxmox VE Backup Job"""

    def __init__(self, backup_id, **kwargs):
        super().__init__(id=backup_id, **kwargs)

        self.all = self.all == 1
        self.vmid = self._split(self.vmid)
        self.exclude = self._split(self.exclude)

    @classmethod
    def from_api(cls, payload):
        values = api_kwargs(PVEBackupJobData, payload)
        return cls(values.pop("id", None), **values)

    @staticmethod
    def _split(value) -> List[str]:
        if isinstance(value, str):
            return value.split(",")
        if value is None:
            return []
        return [str(value)]

    def __str__(self):
        return f"Vm(s): {self.vmid}\n" + format_fields(self, exclude=("vmid",))

    def is_selection_matching(self, vm):
        if self.node is not None and self.node != vm.node:
            return False
        if self.pool is not None:
            return self.pool == vm.pool
        if self.all:
            return str(vm.vmid) not in self.exclude
        return str(vm.vmid) in self.vmid
