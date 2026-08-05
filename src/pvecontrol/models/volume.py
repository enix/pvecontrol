from dataclasses import dataclass, field
from typing import Optional

from pvecontrol.models import api_kwargs, format_fields


@dataclass
class PVEVolumeData:
    volid: str = field(default="")
    format: str = field(default="")
    size: int = field(default=0)
    content: Optional[str] = None
    # the API returns this one as a string, it is converted below
    ctime: Optional[int] = None
    encrypted: Optional[int] = None
    notes: Optional[str] = None
    parent: Optional[str] = None
    path: Optional[str] = None
    protected: Optional[int] = None
    subtype: Optional[str] = None
    used: Optional[int] = None
    verification: Optional[dict] = None
    vmid: Optional[int] = None


class PVEVolume(PVEVolumeData):
    """Proxmox VE Volume"""

    def __init__(self, **kwargs):
        super().__init__(**api_kwargs(PVEVolumeData, kwargs))
        if isinstance(self.ctime, str):
            self.ctime = int(self.ctime)

    def __str__(self):
        return f"Id: {self.volid}\n" + format_fields(self)
