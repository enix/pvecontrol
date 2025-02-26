from datetime import datetime, timedelta
from pvecontrol.sanitycheck.checks import Check, CheckCode, CheckType, CheckMessage


class VmBackups(Check):

    id = "vm_backups"
    type = CheckType.VM
    name = "Check that Vms are backup up on a regular basis"

    def run(self):
        backuped_vms = self._check_is_backed_up()
        self._check_backup_ran_recently(backuped_vms)

    def _check_is_backed_up(self):
        backuped_vms = []
        for vm in self.proxmox.vms:
            vm_backup_jobs = vm.get_backup_jobs(self.proxmox)
            vm_enabled_backup_ids = [backup.id for backup in vm_backup_jobs if backup.enabled == 1]
            if len(vm_enabled_backup_ids) > 0:
                msg = f"Vm {vm.vmid} ({vm.name}) is associated to {len(vm_enabled_backup_ids)} enabled backup job(s)"
                self.add_messages(CheckMessage(CheckCode.OK, msg))
                backuped_vms.append(vm)
            else:
                msg = f"Vm {vm.vmid} ({vm.name}) is not associated to any backup job"
                self.add_messages(CheckMessage(CheckCode.WARN, msg))
        return backuped_vms

    def _check_backup_ran_recently(self, vms):
        minutes_ago = self.proxmox.config["vm"]["max_last_backup"]
        hm_ago = divmod(minutes_ago, 60)
        time_ago = f"{hm_ago[0]:02d} hour(s) and {hm_ago[1]:02d} minute(s)"

        for vm in vms:
            last_backup = vm.get_last_backup(self.proxmox)
            if last_backup is None:
                message = CheckMessage(CheckCode.WARN, f"Vm {vm.vmid} ({vm.name}) has never been backed up yet")
                self.add_messages(message)
                continue
            last_backup_time = datetime.fromtimestamp(last_backup.ctime)
            last_backup_time_str = last_backup_time.strftime("%Y-%m-%d %H:%M:%S")
            if last_backup_time > datetime.now() - timedelta(minutes=minutes_ago):
                message = f"Vm {vm.vmid} ({vm.name}) has been backed up in the last {time_ago}, last backup: {last_backup_time_str}"
                self.add_messages(CheckMessage(CheckCode.OK, message))

            else:
                message = f"Vm {vm.vmid} ({vm.name}) last backup: {last_backup_time_str}"
                self.add_messages(CheckMessage(CheckCode.CRIT, message))
