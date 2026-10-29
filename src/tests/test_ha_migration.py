import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch

from pvecontrol.models.task import PVETask
from pvecontrol.utils import print_task

# As captured on PVE 9.2 when migrating a VM managed by HA: the API answers with a hamigrate task that only
# hands the request to the HA manager, which starts its own qmigrate task about 10 s later
UPID_HAMIGRATE = "UPID:pve-devel-2:0000478E:000359AE:6AE38CD2:hamigrate:110:root@pam:"
UPID_QMIGRATE = "UPID:pve-devel-2:00004790:00035A10:6AE38CDE:qmigrate:110:root@pam:"
UPID_OLD_QMIGRATE = "UPID:pve-devel-2:00003F35:0002EC6A:6AE38BBA:qmigrate:110:root@pam:"
QMIGRATE_ENTRY = {
    "upid": UPID_QMIGRATE,
    "type": "qmigrate",
    "id": "110",
    "node": "pve-devel-2",
    "starttime": 0x6AE38CDE,
}
OLD_QMIGRATE_ENTRY = {
    "upid": UPID_OLD_QMIGRATE,
    "type": "qmigrate",
    "id": "110",
    "node": "pve-devel-2",
    "starttime": 0x6AE38BBA,
    "endtime": 0x6AE38BCE,
    "status": "OK",
}


def ha_service(state):
    """An entry of cluster/ha/status/current for vm:110"""
    return {"id": "service:vm:110", "sid": "vm:110", "type": "service", "state": state, "crm_state": state}


class HaMigrationTestcase(unittest.TestCase):

    def setUp(self):
        api = MagicMock()
        self.endpoints = {
            UPID_HAMIGRATE: self._endpoint([{"status": "stopped", "exitstatus": "OK"}]),
            UPID_QMIGRATE: self._endpoint([{"status": "running"}, {"status": "stopped", "exitstatus": "OK"}]),
        }
        api.nodes.return_value.tasks.side_effect = lambda upid: self.endpoints[upid]
        self.proxmox = MagicMock()
        self.proxmox.get_task.side_effect = lambda upid: PVETask(api, upid)
        self.proxmox.is_node_online.return_value = True
        # The HA manager hasn't started its task on the first poll, an older migration of the VM is listed
        self.cluster_tasks = self.proxmox.api.cluster.tasks.get
        self.cluster_tasks.side_effect = [[OLD_QMIGRATE_ENTRY], [QMIGRATE_ENTRY, OLD_QMIGRATE_ENTRY]]
        # The HA manager records the end of the migration on its next round
        self.ha_status = self.proxmox.api.cluster.ha.status.current.get
        self.ha_status.side_effect = [[ha_service("migrate")], [ha_service("started")]]

    @staticmethod
    def _endpoint(statuses):
        endpoint = MagicMock()
        endpoint.status.get.side_effect = statuses
        endpoint.log.get.return_value = [{"n": 1, "t": "TASK OK"}]
        return endpoint

    def _print_task(self, **options):
        with patch("pvecontrol.utils.time.sleep"), contextlib.redirect_stdout(io.StringIO()) as output:
            task = print_task(self.proxmox, UPID_HAMIGRATE, **options)
        return output.getvalue(), task

    def test_wait_follows_the_ha_migration(self):
        for options in [{"wait": True}, {"follow": True}]:
            self.setUp()
            output, task = self._print_task(**options)
            # The older qmigrate task of the same VM is not mistaken for the requested one
            assert [call.args[0] for call in self.proxmox.get_task.call_args_list] == [UPID_HAMIGRATE, UPID_QMIGRATE]
            assert self.cluster_tasks.call_count == 2
            assert self.endpoints[UPID_QMIGRATE].status.get.call_count == 2
            assert UPID_QMIGRATE in output
            # It returns once the HA manager is done with the migration, so the VM can be migrated again
            assert self.ha_status.call_count == 2
            # The task returned is the one that migrated the VM, node evacuate checks its result
            assert task.upid == UPID_QMIGRATE
            assert task.exitstatus == "OK"

    def test_without_wait_the_request_is_enough(self):
        _, task = self._print_task()
        self.cluster_tasks.assert_not_called()
        self.ha_status.assert_not_called()
        assert task.upid == UPID_HAMIGRATE

    def test_ha_manager_slow_to_settle(self):
        with patch("pvecontrol.utils.HA_MIGRATION_SETTLE_TIMEOUT", 0), self.assertLogs(level="WARNING") as logs:
            self._print_task(wait=True)
        assert "still reports vm:110 as migrating" in "\n".join(logs.output)

    def test_failed_request_is_not_followed(self):
        self.endpoints[UPID_HAMIGRATE] = self._endpoint([{"status": "stopped", "exitstatus": "no such target"}])
        self._print_task(wait=True)
        self.cluster_tasks.assert_not_called()

    def test_ha_manager_never_starts_the_migration(self):
        with patch("pvecontrol.utils.HA_MIGRATION_START_TIMEOUT", 0), self.assertLogs(level="ERROR") as logs:
            with self.assertRaises(SystemExit) as exit_info:
                self._print_task(wait=True)
        assert exit_info.exception.code == 1
        assert f"didn't start the migration requested by {UPID_HAMIGRATE}" in "\n".join(logs.output)
