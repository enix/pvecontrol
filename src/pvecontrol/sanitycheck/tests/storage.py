from pvecontrol.sanitycheck.checks import Check, CheckCode, CheckType, CheckMessage


class DiskUnused(Check):

    id = "disk_unused"
    type = CheckType.STORAGE
    name = "Check disk unused"

    def run(self):
        for storage in self.proxmox.storages:
            if storage.plugintype not in ["lvm", "lvmthin", "zfspool"]:
                continue
            for image in storage.images:
                self._check_disk_is_used(image)

    def _check_disk_is_used(self, image):
        vmid_parsed = image.volid.split("-")[1]
        if image.vmid == int(vmid_parsed):
            msg = f"Disk '{image.volid}' is used"
            self.add_messages(CheckMessage(CheckCode.OK, msg))
        else:
            msg = f"Disk '{image.volid}' is not used"
            self.add_messages(CheckMessage(CheckCode.CRIT, msg))
