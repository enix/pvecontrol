from datetime import datetime, timedelta
from pvecontrol.sanitycheck.checks import Check, CheckCode, CheckType, CheckMessage
from pvecontrol.storage import PVEStorage


class VmBackups(Check):

    id = "vm_backups"
    type = CheckType.VM
    name = "Check that Vms are backup up on a regular basis"

    def run(self):
        backuped_vms = self._check_is_backed_up()
        self._check_backup_ran_recently(backuped_vms)

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

    def _check_backup_ran_recently(self, vms):
        minutes_ago = self.proxmox.config["vm"]["max_last_backup"]
        hm_ago = divmod(minutes_ago, 60)
        time_ago = f"{hm_ago[0]:02d} hour(s) and {hm_ago[1]:02d} minute(s) ago"

        for vm in vms:
            last_backup = self._get_vm_last_backup(vm)
            last_backup_time = datetime.fromtimestamp(last_backup["ctime"])
            msg_template = f"Vm {vm.vmid} ({vm.name}) has been backed up {{}} than {time_ago} ({last_backup_time.strftime('%Y-%m-%d %H:%M:%S')})"
            if last_backup_time > datetime.now() - timedelta(minutes=minutes_ago):
                msg = msg_template.format("less")
                self.add_messages(CheckMessage(CheckCode.OK, msg))
            else:
                msg = msg_template.format("more")
                self.add_messages(CheckMessage(CheckCode.WARN, msg))

    def _get_vm_backup_jobs(self, vm, backup_jobs):
        vm_backups = []
        for backup in backup_jobs:
            if str(vm.vmid) in backup["vmid"].split(","):
                vm_backups.append(backup)
        return vm_backups

    def _get_vm_backups(self, vm):
        backups = []
        for item in PVEStorage.get_grouped_list(self.proxmox):
            backups.extend(item["storage"].get_content("backup"))

        return [backup for backup in backups if backup["vmid"] == vm.vmid]

    def _get_vm_last_backup(self, vm):
        vm_backups = sorted(self._get_vm_backups(vm), key=lambda x: x["ctime"])
        return vm_backups[-1] if len(vm_backups) > 0 else None
