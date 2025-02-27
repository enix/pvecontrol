class PVEBackupJob:
    """Proxmox VE Backup Job"""

    _default_kwargs = {
        "all": 0,
        "compress": None,
        "enabled": None,
        "exclude": "",
        "fleecing": None,
        "mode": None,
        "next-run": None,
        "node": None,
        "notes-template": None,
        "pool": None,
        "prune-backups": None,
        "schedule": None,
        "storage": None,
        "type": None,
        "vmid": "",
    }

    def __init__(self, backup_id, **kwargs):
        self.id = backup_id

        for k, v in self._default_kwargs.items():
            self.__setattr__(k, kwargs.get(k, v))

        self.all = self.all == 1
        self.vmid = self.vmid.split(",")
        self.exclude = self.exclude.split(",")

    def __str__(self):
        output = f"Vm(s): {self.vmid}\n" + f"Id: {self.id}\n"
        for key in self._default_kwargs:
            output += f"{key.capitalize()}: {self.__getattribute__(key)}\n"
        return output

    def is_selection_matching(self, vm):
        if self.node is not None and self.node != vm.node:
            return False
        if self.pool is not None:
            return self.pool == vm.pool
        if self.all:
            return str(vm.vmid) not in self.exclude
        return str(vm.vmid) in self.vmid
