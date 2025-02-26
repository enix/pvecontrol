from pvecontrol.vm import VmStatus
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
