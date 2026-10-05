from types import SimpleNamespace
from unittest.mock import Mock, patch

from click.testing import CliRunner

from pvecontrol.actions.node import evacuate
from pvecontrol.models.vm import PVEVm
from tests.fixtures.api import fake_vm
from tests.testcase import PVEControlTestcase


class EvacuateTestcase(PVEControlTestcase):
    """pve-devel-1 hosts VM 100 (running) and VM 101 (stopped)"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.vms[1] = fake_vm(101, self.nodes[0], status="stopped")

    def _cluster_config(self):
        config = super()._cluster_config()
        config["node"]["memoryminimum"] = 1073741824
        return config

    def _evacuate(self, args, confirmation="yes", task_exitstatus="OK", task_running=False):
        task = Mock(exitstatus=task_exitstatus)
        task.running.return_value = task_running
        task.vanished.return_value = False
        with (
            patch("pvecontrol.actions.node.PVECluster.create_from_config", return_value=self.cluster),
            patch.object(self.cluster, "refresh"),
            patch("pvecontrol.actions.node.print_task", return_value=task),
            patch.object(PVEVm, "migrate", autospec=True, return_value="UPID") as migrate,
        ):
            result = CliRunner().invoke(
                evacuate, args, obj={"args": SimpleNamespace(cluster="test")}, input=f"{confirmation}\n"
            )
        calls = {call.args[0].vmid: call.args[1:] for call in migrate.call_args_list}
        return result, calls

    def test_unknown_node(self):
        with self.assertLogs("root", level="ERROR") as log:
            result, calls = self._evacuate(["pve-unknown"])
        assert result.exit_code == 1
        assert calls == {}
        assert any("pve-unknown does not exist" in msg for msg in log.output)
        assert "does not exist" not in result.stdout

    def test_no_target_available(self):
        with self.assertLogs("root", level="ERROR") as log:
            result, calls = self._evacuate(["pve-devel-1", "pve-devel-1"])
        assert result.exit_code == 1
        assert calls == {}
        assert any("No target node available" in msg for msg in log.output)

    def test_migration(self):
        result, calls = self._evacuate(["pve-devel-1", "--online"])
        assert result.exit_code == 0
        assert list(calls) == [100]

    def test_dry_run(self):
        result, calls = self._evacuate(["pve-devel-1", "--online", "--dry-run"])
        assert result.exit_code == 0
        assert calls == {}

    def test_aborted(self):
        with self.assertLogs("root", level="ERROR"):
            result, calls = self._evacuate(["pve-devel-1", "--online"], confirmation="no")
        assert result.exit_code == 1
        assert calls == {}

    def test_failed_migration(self):
        with self.assertLogs("root", level="ERROR") as log:
            result, _ = self._evacuate(["pve-devel-1", "--online", "--wait"], task_exitstatus="migration aborted")
        assert result.exit_code == 1
        assert any("Migration failed for VM(s): 100" in msg for msg in log.output)

    def test_running_task_is_not_a_failure(self):
        result, _ = self._evacuate(["pve-devel-1", "--online"], task_exitstatus="", task_running=True)
        assert result.exit_code == 0


class EvacuateNoCapacityTestcase(PVEControlTestcase):
    """Default test config reserves more memory than any node has"""

    def test_no_target_for_vms(self):
        with (
            patch("pvecontrol.actions.node.PVECluster.create_from_config", return_value=self.cluster),
            patch.object(PVEVm, "migrate", autospec=True) as migrate,
            self.assertLogs("root", level="WARNING") as log,
        ):
            result = CliRunner().invoke(
                evacuate, ["pve-devel-1", "--online"], obj={"args": SimpleNamespace(cluster="test")}
            )
        assert result.exit_code == 1
        migrate.assert_not_called()
        assert any("No target found for VM 100" in msg for msg in log.output)
        assert any("No VM can be migrated" in msg for msg in log.output)
