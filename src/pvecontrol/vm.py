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
        self.api = api

        self.name = kwargs.get("name", "")
        self.lock = kwargs.get("lock", "")
        self.cpus = kwargs.get("cpus", 0)
        self.maxdisk = kwargs.get("maxdisk", 0)
        self.maxmem = kwargs.get("maxmem", 0)
        self.uptime = kwargs.get("uptime", 0)
        self.tags = kwargs.get("tags", "")
        self.template = kwargs.get("template", 0)

        self.config = self.api.nodes(self.node).qemu(vmid).config.get()

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
        check = self.api.nodes(self.node).qemu(self.vmid).migrate.get(**options)
        #    logging.debug("Migration check: %s"%check)
        options["online"] = int(online)
        if len(check["local_disks"]) > 0:
            options["with-local-disks"] = int(True)

        upid = self.api.nodes(self.node).qemu(self.vmid).migrate.post(**options)
        return upid
