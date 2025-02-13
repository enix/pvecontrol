class PVEBackupJob:
    """Proxmox VE Backup Job"""

    _default_kwargs = {
        "compress": None,
        "enabled": None,
        "fleecing": None,
        "mode": None,
        "next-run": None,
        "notes-template": None,
        "prune-backups": None,
        "schedule": None,
        "storage": None,
        "type": None,
        "vmid": None,
    }

    def __init__(self, backup_id, **kwargs):
        self.id = backup_id

        for k, v in self._default_kwargs.items():
            self.__setattr__(k, kwargs.get(k, v))

    def __str__(self):
        output = f"Vm(s): {self.vmid}\n" + f"Id: {self.id}\n"
        for key in self._default_kwargs:
            output += f"{key.capitalize()}: {self.__getattribute__(key)}\n"
        return output
