import re

from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs

import responses

from click.testing import CliRunner

from pvecontrol.actions.node import evacuate
from pvecontrol.models.task import PVETask
from pvecontrol.models.vm import PVEVm
from tests.fixtures.api import fake_ha_manager_status, fake_vm
from tests.testcase import PVEControlTestcase

MAINTENANCE_URL = re.compile(r"https://host:8006/api2/json/nodes/[^/]+/maintenance")
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


class EvacuateHaMaintenanceBaseTestcase(EvacuateBaseTestcase):
    """pve-devel-1 also hosts VM 105 (running) and VM 106 (stopped), HA manages VMs 100 and 106, the nodes run
    pve-manager 9.2.33"""

    node_status = "online"
    node_request = False
    # Set by _evacuate_ha(): the wait_drained() and refresh() mocks, and the logs of the run
    wait = refresh = None
    log = ()

    def _build_fixtures(self):
        super()._build_fixtures()
        self.vms[0]["hastate"] = "started"
        self.vms.append(fake_vm(105, self.nodes[0]))
        self.vms.append(fake_vm(106, self.nodes[0], status="stopped", hastate="stopped"))
        self.ha_manager_status = fake_ha_manager_status(
            node_status={"pve-devel-1": self.node_status, "pve-devel-2": "online", "pve-devel-3": "online"},
            node_request=["pve-devel-1"] if self.node_request else None,
            service_status={"vm:100": "pve-devel-1", "vm:106": "pve-devel-1"},
        )

    def _post_setup(self):
        super()._post_setup()
        self.cluster.version = {"version": "9.2.33", "release": "9.2"}
        self.cluster.find_node("pve-devel-1").version = {"version": "9.2.33", "release": "9.2"}

    def _drain(self):
        """What refresh() reads once the HA manager has moved VM 100 to pve-devel-2"""
        srcnode = self.cluster.find_node("pve-devel-1")
        # refresh() also runs after each migration
        for vm in [vm for vm in srcnode.vms if vm.vmid == 100]:
            srcnode.vms.remove(vm)
            self.cluster.find_node("pve-devel-2").allocatedmem += vm.maxmem

    # pylint: disable=too-many-arguments
    def _evacuate_ha(self, args, answers="y\ny\n", drain=True, wait_drained=None, put_status=200, config_file=None):
        task = PVETask(None, UPID, summary={"endtime": 1, "status": "OK"})
        with (
            responses.RequestsMock(assert_all_requests_are_fired=False) as api,
            patch("pvecontrol.actions.node.PVECluster.create_from_config", return_value=self.cluster),
            patch.object(self.cluster, "refresh", side_effect=self._drain if drain else None) as refresh,
            patch("pvecontrol.actions.node.wait_drained", side_effect=wait_drained) as wait,
            patch("pvecontrol.actions.node.print_task", return_value=task),
            patch.object(PVEVm, "migrate", autospec=True, return_value="UPID") as migrate,
            self.assertLogs("root", level="DEBUG") as log,
        ):
            api.put(MAINTENANCE_URL, status=put_status, json={"data": None})
            result = CliRunner().invoke(
                evacuate,
                ["pve-devel-1", "--ha-maintenance", *args],
                obj={"args": SimpleNamespace(cluster="test", config_file=config_file)},
                input=answers,
            )
            puts = [(call.request.url, parse_qs(call.request.body)) for call in api.calls]
        self.wait, self.refresh, self.log = wait, refresh, log.output
        return result, puts, [call.args[0].vmid for call in migrate.call_args_list]

    def _logged(self, text):
        return any(text in msg for msg in self.log)


class EvacuateHaMaintenanceModeTestcase(EvacuateHaMaintenanceBaseTestcase):

    def test_ha_maintenance(self):
        result, puts, migrated = self._evacuate_ha(["--online"])
        assert result.exit_code == 0, result.output
        assert puts == [("https://host:8006/api2/json/nodes/pve-devel-1/maintenance", {"maintenance-mode": ["enable"]})]
        assert "The HA manager will move the HA VM(s) of node pve-devel-1 away: 100" in result.stdout
        self.wait.assert_called_once_with(self.cluster, "pve-devel-1", 900)
        # The drained node is read again before the plan, VM 100 is gone: only VM 105 is migrated
        assert migrated == [105]
        assert "Migrating VM 105" in result.stdout
        # A stopped HA VM is left to the HA manager, even without --no-skip-stopped
        assert self._logged("VM 106 (vm-106) is managed by HA (stopped), left to the HA manager")
        assert self._logged(
            "Node pve-devel-1 stays in HA maintenance mode, leave it with: "
            "pvecontrol -c test ha maintenance-disable pve-devel-1"
        )

    def test_commands_use_the_config_file(self):
        result, _, _ = self._evacuate_ha(["--online"], config_file="/home/me/my config.yaml")
        assert result.exit_code == 0, result.output
        assert self._logged(
            "leave it with: pvecontrol -c test --config '/home/me/my config.yaml' ha maintenance-disable pve-devel-1"
        )

    def test_timeout(self):
        result, _, migrated = self._evacuate_ha(["--online", "--timeout", "60"])
        assert result.exit_code == 0, result.output
        self.wait.assert_called_once_with(self.cluster, "pve-devel-1", 60)
        assert migrated == [105]

    def test_ha_vm_left_on_node(self):
        # A stopped HA resource doesn't count as active: the node is drained with it
        result, _, migrated = self._evacuate_ha(["--online", "--no-skip-stopped"], drain=False)
        assert result.exit_code == 0, result.output
        assert migrated == [101, 105]
        assert self._logged("VM 100 (vm-100) is managed by HA (started), left to the HA manager")

    def test_maintenance_declined(self):
        result, puts, migrated = self._evacuate_ha(["--online"], answers="n\n")
        assert result.exit_code == 1
        assert puts == []
        self.wait.assert_not_called()
        assert migrated == []
        assert not self._logged("stays in HA maintenance mode")

    def test_plan_declined(self):
        result, puts, migrated = self._evacuate_ha(["--online"], answers="y\nn\n")
        assert result.exit_code == 1
        assert len(puts) == 1
        assert migrated == []
        assert self._logged("Node pve-devel-1 stays in HA maintenance mode")

    def test_drain_timeout(self):
        result, puts, migrated = self._evacuate_ha(["--online"], wait_drained=SystemExit(1))
        assert result.exit_code == 1
        assert len(puts) == 1
        self.refresh.assert_not_called()
        assert migrated == []
        # The request may still be queued: the node is not said to be in maintenance
        assert not self._logged("stays in HA maintenance mode")
        assert self._logged(
            "The HA maintenance mode of node pve-devel-1 is requested, it may not be effective yet: "
            "check it with pvecontrol -c test ha status pve-devel-1, "
            "cancel it with: pvecontrol -c test ha maintenance-disable pve-devel-1"
        )

    def test_maintenance_refused(self):
        result, _, migrated = self._evacuate_ha(["--online"], put_status=500)
        assert result.exit_code == 1
        self.wait.assert_not_called()
        assert migrated == []
        assert not self._logged("stays in HA maintenance mode")

    def test_dry_run(self):
        result, puts, migrated = self._evacuate_ha(["--online", "--dry-run"], answers="y\n")
        assert result.exit_code == 0, result.output
        assert puts == []
        self.wait.assert_not_called()
        assert "HA maintenance mode of node pve-devel-1 is not enabled, HA VM(s): 100, 106" in result.stdout
        assert self._logged("the plan doesn't account for the HA VMs")
        assert self._logged("VM 100 (vm-100) is managed by HA (started), left to the HA manager")
        assert "Migrating VM 105" in result.stdout
        assert migrated == []
        assert not self._logged("stays in HA maintenance mode")

    def test_old_pve_manager(self):
        self.cluster.find_node("pve-devel-1").version = {"version": "9.1.4", "release": "9.1"}
        result, puts, migrated = self._evacuate_ha(["--online"])
        assert result.exit_code == 1
        assert puts == []
        assert migrated == []
        assert self._logged("The maintenance API requires pve-manager 9.2.33 or later, node pve-devel-1 runs 9.1.4")


class EvacuateAlreadyInHaMaintenanceTestcase(EvacuateHaMaintenanceBaseTestcase):
    """pve-devel-1 is already in HA maintenance, still draining"""

    node_status = "maintenance"
    node_request = True

    def test_ha_maintenance(self):
        result, puts, migrated = self._evacuate_ha(["--online"], answers="y\n")
        assert result.exit_code == 0, result.output
        assert puts == []
        assert self._logged("Node pve-devel-1 is already in HA state maintenance")
        self.wait.assert_called_once_with(self.cluster, "pve-devel-1", 900)
        assert migrated == [105]


class EvacuateLeavingHaMaintenanceTestcase(EvacuateHaMaintenanceBaseTestcase):
    """pve-devel-1 is in HA maintenance, but the CRM dropped its request: it is leaving the maintenance mode"""

    node_status = "maintenance"

    def test_ha_maintenance(self):
        result, puts, migrated = self._evacuate_ha(["--online"])
        assert result.exit_code == 0, result.output
        # Waiting without requesting it again would wait for a node going back online
        assert puts == [("https://host:8006/api2/json/nodes/pve-devel-1/maintenance", {"maintenance-mode": ["enable"]})]
        assert not self._logged("already in HA state")
        assert migrated == [105]


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
