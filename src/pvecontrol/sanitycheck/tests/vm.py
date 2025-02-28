from pvecontrol.models.vm import VmStatus
from pvecontrol.sanitycheck.checks import Check, CheckCode, CheckType, CheckMessage


class VmsStartOnBoot(Check):

    id = "vms_start_on_boot"
    type = CheckType.VM
    name = "Check vms startonboot option"

    def run(self):
        vms = [vm for vm in self.proxmox.vms if vm.template == 0]
        for vm in vms:
            self._check_vm_statonboot_option(vm)

    def _check_vm_statonboot_option(self, vm):
        if self._vm_has_startonboot_enabled(vm):
            self._check_vm_statonboot_enabled(vm)
        else:
            self._check_vm_statonboot_disabled(vm)

    def _vm_has_startonboot_enabled(self, vm):
        return vm.config.get("onboot", 0) == 1

    def _check_vm_statonboot_enabled(self, vm):
        if vm.status == VmStatus.RUNNING:
            msg = f"VM '{vm.vmid}/{vm.name}' has the good 'startonboot' option"
            self.add_messages(CheckMessage(CheckCode.OK, msg))
        elif vm.status == VmStatus.STOPPED:
            msg = f"VM '{vm.vmid}/{vm.name}' is stopped but 'startonboot' is set to true"
            self.add_messages(CheckMessage(CheckCode.CRIT, msg))

    def _check_vm_statonboot_disabled(self, vm):
        if vm.status == VmStatus.STOPPED:
            msg = f"VM '{vm.vmid}/{vm.name}' has the good 'startonboot' option"
            self.add_messages(CheckMessage(CheckCode.OK, msg))
        elif vm.status == VmStatus.RUNNING:
            msg = f"VM '{vm.vmid}/{vm.name}' is running but 'startonboot' is set to false"
            self.add_messages(CheckMessage(CheckCode.CRIT, msg))


class DiskUnused(Check):

    id = "disk_unused"
    type = CheckType.STORAGE
    name = "Check disk unused"

    def run(self):
        for vm in self.proxmox.vms:
            self._check_vm_disk_is_unused(vm)

        for storage in self.proxmox.storages:
            if storage.plugintype == "s3":
                # in enix specific case, we don't want to check s3 storage
                continue

            self._check_storage_disk_is_unused(storage)

    def _check_vm_disk_is_unused(self, vm):
        for key in vm.config.keys():
            # key are like unused[n], ie: unused0, unused1 ...
            if "unused" not in key:
                continue
            msg = f"Disk '{key}' is not used on vm {vm.vmid}/{vm.name}"
            self.add_messages(CheckMessage(CheckCode.CRIT, msg))

    def _check_storage_disk_is_unused(self, storage):
        node = self.proxmox.find_node(storage.node)
        node_vms_ids = [vm.vmid for vm in node.vms]
        for image in storage.get_content("images"):
            if image["vmid"] not in node_vms_ids:
                msg = f"Disk '{image['volid']}' is not used, vm {image['vmid']} doesn't exists"
                self.add_messages(CheckMessage(CheckCode.CRIT, msg))
