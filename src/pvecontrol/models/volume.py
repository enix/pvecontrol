from dataclasses import dataclass, field


@dataclass
class PVEVolumeData:
    volid: str = field(default="")
    volume_format: str = field(default="")
    size: int = field(default=0)
    content: str = field(default="")

    # is a string in API... convert it upon super() call...
    ctime: int = field(default=0)
    # unsure with those types... just porting _default_kwargs
    encrypted: object = None
    note: object = None
    parent: object = None
    path: object = None
    protected: object = None
    subtype: object = None
    used: object = None
    verification: object = None
    vmid: int = field(default=0)


class PVEVolume(PVEVolumeData):
    """Proxmox VE Volume"""

    def __init__(self, **kwargs):
        _values = {k: v for k, v in kwargs.items() if hasattr(PVEVolumeData, k)}
        super().__init__(**_values)
        if isinstance(self.ctime, str):
            self.ctime = int(self.ctime)

    def __str__(self):
        return "\n".join([f"{k.capitalize()}: {v}" for k, v in self.__dict__.items()])
