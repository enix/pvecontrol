from pvecontrol.sanitycheck.checks import Check, CheckCode, CheckType, CheckMessage


class VmBackups(Check):

    id = "vm_backups"
    type = CheckType.VM
    name = "Check that Vms are backup up on a regular basis"

    def run(self):
        self._check_is_backed_up()

    def _check_is_backed_up(self):
        backup_jobs = self.proxmox.api.cluster.backup.get()
        backuped_vms = []
        for vm in self.proxmox.vms:
            vm_backup_jobs = self._get_vm_backup_jobs(vm, backup_jobs)
            vm_enabled_backup_ids = [backup["id"] for backup in vm_backup_jobs if backup["enabled"] == 1]
            if len(vm_enabled_backup_ids) > 0:
                msg = f"Vm {vm.vmid} ({vm.name}) is associated to {len(vm_enabled_backup_ids)} enabled backup job(s)"
                self.add_messages(CheckMessage(CheckCode.OK, msg))
                backuped_vms.append(vm)
            else:
                msg = f"Vm {vm.vmid} ({vm.name}) is not associated to any backup job"
                self.add_messages(CheckMessage(CheckCode.CRIT, msg))
        return backuped_vms

    def _get_vm_backup_jobs(self, vm, backup_jobs):
        vm_backups = []
        for backup in backup_jobs:
            if str(vm.vmid) in backup["vmid"].split(","):
                vm_backups.append(backup)
        return vm_backups
