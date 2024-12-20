class PVEVolume:
    """Proxmox VE Volume"""

    _default_kwargs = {
        "content": None,
        "ctime": None,
        "encrypted": None,
        "notes": None,
        "parent": None,
        "path": None,
        "protected": None,
        "subtype": None,
        "used": None,
        "verification": None,
        "vmid": None,
    }

    def __init__(self, volid, volume_format, size, **kwargs):
        self.volid = volid
        self.format = volume_format
        self.size = size

        for k, v in self._default_kwargs.items():
            self.__setattr__(k, kwargs.get(k, v))
