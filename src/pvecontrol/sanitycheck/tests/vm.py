from pvecontrol.vm import VmStatus
from pvecontrol.sanitycheck.checks import Check, CheckCode, CheckType, CheckMessage


class VmsStartOnBoot(Check):

    id = "vms_start_on_boot"
    type = CheckType.VM
    name = "Check vms startonboot option"

    def run(self):
        vms = [vm for vm in self.proxmox.vms if vm.template == 0]
        for vm in vms:
            if vm.config.get("onboot") == 1 and vm.status == VmStatus.STOPPED:
                msg = f"VM '{vm.vmid}/{vm.name}' is stopped but 'startonboot' is set to true"
                self.add_messages(CheckMessage(CheckCode.CRIT, msg))
            elif vm.config.get("onboot") == 1 and vm.status == VmStatus.RUNNING:
                msg = f"VM '{vm.vmid}/{vm.name}' as the good 'startonboot' option"
                self.add_messages(CheckMessage(CheckCode.OK, msg))

            if (vm.config.get("onboot") is None or vm.config.get("onboot") == 0) and vm.status == VmStatus.RUNNING:
                msg = f"VM '{vm.vmid}/{vm.name}' is running but 'startonboot' is set to false"
                self.add_messages(CheckMessage(CheckCode.CRIT, msg))
            elif (vm.config.get("onboot") is None or vm.config.get("onboot") == 0) and vm.status == VmStatus.STOPPED:
                msg = f"VM '{vm.vmid}/{vm.name}' as the good 'startonboot' option"
                self.add_messages(CheckMessage(CheckCode.OK, msg))
