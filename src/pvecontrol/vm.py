from enum import Enum


COLUMNS = ["vmid", "name", "status", "node", "cpus", "maxmem", "maxdisk"]


class VmStatus(Enum):
    STOPPED = 0
    RUNNING = 1


class PVEVm:
    """Proxmox VE Qemu VM"""

    _api = None

    def __init__(self, api, node, vmid, status, kwargs=None):
        if not kwargs:
            kwargs = {}

        self.vmid = vmid
        self.status = VmStatus[status.upper()]
        self.node = node
        self._api = api

        self.name = kwargs.get("name", "")
        self.lock = kwargs.get("lock", "")
        self.cpus = kwargs.get("maxcpu", 0)
        self.maxdisk = kwargs.get("maxdisk", 0)
        self.maxmem = kwargs.get("maxmem", 0)
        self.uptime = kwargs.get("uptime", 0)
        self.tags = kwargs.get("tags", "")
        self.template = kwargs.get("template", 0)

        self._config = None

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
        vm_backups = []
        for backup in proxmox.backup_jobs:
            if str(self.vmid) in backup.vmid.split(","):
                vm_backups.append(backup)
        return vm_backups

    def get_backups(self, proxmox):
        return [backup for backup in proxmox.backups if backup.vmid == self.vmid]

    def get_last_backup(self, proxmox):
        backups = sorted(self.get_backups(proxmox), key=lambda x: x.ctime)
        return backups[-1] if len(backups) > 0 else None
