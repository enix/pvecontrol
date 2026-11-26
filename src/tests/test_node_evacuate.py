from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from pvecontrol.actions.node import evacuate
from pvecontrol.models.task import PVETask
from pvecontrol.models.vm import PVEVm
from tests.fixtures.api import fake_ha_manager_status, fake_vm
from tests.testcase import PVEControlTestcase

UPID = "UPID:pve-devel-1:00001234:00005678:6AE38CD2:qmigrate:100:root@pam:"


class EvacuateBaseTestcase(PVEControlTestcase):
    """pve-devel-1 hosts VM 100 (running) and VM 101 (stopped)"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.vms[1] = fake_vm(101, self.nodes[0], status="stopped")

    def _cluster_config(self):
        config = super()._cluster_config()
        config["node"]["memoryminimum"] = 1073741824
        return config

    def _post_setup(self):
        # The HA state of the targets is read lazily, while the api is mocked
        _ = self.cluster.node_ha_states

    def _evacuate(self, args, confirmation="yes", task_exitstatus="OK", task_running=False):
        # cluster/tasks lists a finished task with its exit status and endtime, a running one without both
        task = PVETask(None, UPID, summary={} if task_running else {"endtime": 1, "status": task_exitstatus})
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


class EvacuateTestcase(EvacuateBaseTestcase):

    def test_unknown_node(self):
        with self.assertLogs("root", level="ERROR") as log:
            result, calls = self._evacuate(["pve-unknown"])
        assert result.exit_code == 1
        assert calls == {}
        assert any("pve-unknown does not exist" in msg for msg in log.output)
        assert "does not exist" not in result.stdout

    def test_no_target_available(self):
        with self.assertLogs("root", level="WARNING") as log:
            result, calls = self._evacuate(["pve-devel-1", "pve-devel-1", "--online"])
        assert result.exit_code == 1
        assert calls == {}
        assert any("No target node available" in msg for msg in log.output)
        assert any("not fully evacuated, no target for VM(s): 100" in msg for msg in log.output)

    def test_empty_node_without_target(self):
        # pve-devel-3 hosts no VM: there is nothing to evacuate, whatever the targets
        with self.assertLogs("root", level="INFO") as log:
            result, calls = self._evacuate(["pve-devel-3", "pve-devel-3"])
        assert result.exit_code == 0
        assert calls == {}
        assert any("No VM to migrate" in msg for msg in log.output)

    def test_migration(self):
        result, calls = self._evacuate(["pve-devel-1", "--online"])
        assert result.exit_code == 0
        assert list(calls) == [100]
        assert calls[100][1] is True

    def test_running_vm_skipped_without_online(self):
        with self.assertLogs("root", level="WARNING") as log:
            result, calls = self._evacuate(["pve-devel-1"])
        assert result.exit_code == 1
        assert calls == {}
        assert any("VM 100 (vm-100) is running, use --online" in msg for msg in log.output)
        assert any("running VM(s) need --online: 100" in msg for msg in log.output)

    def test_stopped_vm_migrated_without_online(self):
        with self.assertLogs("root", level="WARNING") as log:
            result, calls = self._evacuate(["pve-devel-1", "--no-skip-stopped"])
        assert result.exit_code == 1
        assert list(calls) == [101]
        assert calls[101][1] is False
        assert any("running VM(s) need --online: 100" in msg for msg in log.output)

    def test_running_and_stopped_vms_with_online(self):
        result, calls = self._evacuate(["pve-devel-1", "--no-skip-stopped", "--online"])
        assert result.exit_code == 0
        assert list(calls) == [100, 101]
        assert calls[100][1] is True

    def test_dry_run(self):
        result, calls = self._evacuate(["pve-devel-1", "--online", "--dry-run"])
        assert result.exit_code == 0
        assert calls == {}

    def test_aborted(self):
        with self.assertLogs("root", level="ERROR") as log:
            result, calls = self._evacuate(["pve-devel-1", "--online"], confirmation="no")
        assert result.exit_code == 1
        assert any("Aborting" in msg for msg in log.output)
        assert "Aborting" not in result.stdout
        assert calls == {}

    def test_failed_migration(self):
        with self.assertLogs("root", level="ERROR") as log:
            result, _ = self._evacuate(["pve-devel-1", "--online", "--wait"], task_exitstatus="migration aborted")
        assert result.exit_code == 1
        assert any("Migration failed for VM(s): 100" in msg for msg in log.output)

    def test_migration_with_warnings_is_not_a_failure(self):
        result, calls = self._evacuate(["pve-devel-1", "--online", "--wait"], task_exitstatus="WARNINGS: 1")
        assert result.exit_code == 0
        assert list(calls) == [100]

    def test_running_task_is_not_a_failure(self):
        result, _ = self._evacuate(["pve-devel-1", "--online"], task_exitstatus="", task_running=True)
        assert result.exit_code == 0


class EvacuateHaMaintenanceTestcase(EvacuateBaseTestcase):
    """pve-devel-2 is in HA maintenance, pve-devel-3 has its maintenance mode requested"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.ha_manager_status = fake_ha_manager_status(
            node_status={"pve-devel-1": "online", "pve-devel-2": "maintenance", "pve-devel-3": "online"},
            node_request=["pve-devel-2", "pve-devel-3"],
        )

    def test_maintenance_nodes_are_not_targets(self):
        with self.assertLogs("root", level="WARNING") as log:
            result, calls = self._evacuate(["pve-devel-1", "--online"])
        assert result.exit_code == 1
        assert calls == {}
        assert any("pve-devel-2 is in HA state maintenance, it is not a target" in msg for msg in log.output)
        assert any("pve-devel-3 is in HA state maintenance_requested, it is not a target" in msg for msg in log.output)
        assert any("no target for VM(s): 100" in msg for msg in log.output)

    def test_explicit_maintenance_target_skipped(self):
        with self.assertLogs("root", level="WARNING") as log:
            result, calls = self._evacuate(["pve-devel-1", "pve-devel-*", "--online"])
        assert result.exit_code == 1
        assert calls == {}
        assert any("Target node pve-devel-2 is in HA state maintenance, skipping" in msg for msg in log.output)
        assert any("Target node pve-devel-3 is in HA state maintenance_requested" in msg for msg in log.output)


class EvacuateHaOnlineTargetTestcase(EvacuateBaseTestcase):
    """Only pve-devel-2 is in HA maintenance: pve-devel-3 takes the VM"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.ha_manager_status = fake_ha_manager_status(
            node_status={"pve-devel-1": "online", "pve-devel-2": "maintenance", "pve-devel-3": "online"}
        )

    def test_migration(self):
        result, calls = self._evacuate(["pve-devel-1", "--online"])
        assert result.exit_code == 0
        assert list(calls) == [100]
        assert calls[100][0] == "pve-devel-3"


class EvacuateFilterTestcase(EvacuateBaseTestcase):
    """pve-devel-1 also hosts VM 105 (running, tagged noevacuate), HA doesn't manage VM 101"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.vms[0]["hastate"] = "started"
        self.vms.append(fake_vm(105, self.nodes[0], hastate="started") | {"tags": "prod;noevacuate"})

    def _evacuate_all(self, *args):
        return self._evacuate(["pve-devel-1", "--online", "--no-skip-stopped", *args])

    def test_no_filter(self):
        result, calls = self._evacuate_all()
        assert result.exit_code == 0
        assert list(calls) == [100, 101, 105]

    def test_exclude(self):
        with self.assertLogs("root", level="INFO") as log:
            result, calls = self._evacuate_all("--exclude", "name", "^vm-100$")
        assert result.exit_code == 0
        assert list(calls) == [101, 105]
        assert any("VM 100 (vm-100) is excluded" in msg for msg in log.output)

    def test_exclude_tag(self):
        result, calls = self._evacuate_all("--exclude", "tags", "noevacuate")
        assert result.exit_code == 0
        assert list(calls) == [100, 101]

    def test_excludes_any(self):
        result, calls = self._evacuate_all("--exclude", "tags", "noevacuate", "--exclude", "vmid", "^100$")
        assert result.exit_code == 0
        assert list(calls) == [101]

    def test_filter(self):
        result, calls = self._evacuate_all("--filter", "vmid", "^10[15]$")
        assert result.exit_code == 0
        assert list(calls) == [101, 105]

    def test_filters_all(self):
        result, calls = self._evacuate_all("--filter", "vmid", "^10[15]$", "--filter", "status", "^running$")
        assert result.exit_code == 0
        assert list(calls) == [105]

    def test_filter_and_exclude(self):
        result, calls = self._evacuate_all("--filter", "status", "running", "--exclude", "tags", "noevacuate")
        assert result.exit_code == 0
        assert list(calls) == [100]

    def test_exclude_ha_managed(self):
        result, calls = self._evacuate_all("--filter", "ha_state", "^-$")
        assert result.exit_code == 0
        assert list(calls) == [101]

    def test_filter_on_displayed_value(self):
        # Sizes are matched as vm list displays them
        result, calls = self._evacuate_all("--filter", "maxmem", "^1.0 GiB$", "--exclude", "vmid", "^10[01]$")
        assert result.exit_code == 0
        assert list(calls) == [105]

    def test_excluded_vms_are_not_left_behind(self):
        # A running VM left on purpose needs no --online and doesn't fail the evacuation
        with self.assertLogs("root", level="INFO") as log:
            result, calls = self._evacuate(["pve-devel-1", "--exclude", "status", "running"])
        assert result.exit_code == 0
        assert calls == {}
        assert any("No VM to migrate" in msg for msg in log.output)
        assert not any("not fully evacuated" in msg for msg in log.output)

    def test_unknown_column(self):
        result, calls = self._evacuate_all("--exclude", "unknown", "x")
        assert result.exit_code == 2
        assert calls == {}
        assert "'unknown' is not one of" in result.output

    def test_invalid_regexp(self):
        result, calls = self._evacuate_all("--filter", "name", "(")
        assert result.exit_code == 2
        assert calls == {}
        assert "invalid regular expression: '('" in result.output


class EvacuateNoCapacityTestcase(PVEControlTestcase):
    """Default test config reserves more memory than any node has"""

    def _post_setup(self):
        _ = self.cluster.node_ha_states

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
        assert any("no target for VM(s): 100" in msg for msg in log.output)
