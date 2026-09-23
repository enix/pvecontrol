import json

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import responses

from click.testing import CliRunner

from pvecontrol import pvecontrol
from pvecontrol.actions.vm import unlock
from pvecontrol.utils import OutputFormats
from tests.testcase import PVEControlTestcase
from tests.fixtures.api import fake_vm


class PVEVmUnlockTestcase(PVEControlTestcase):

    def _build_fixtures(self):
        super()._build_fixtures()
        # vm 100 runs on pve-devel-1 and is locked
        self.vms[0]["lock"] = "backup"

    def _invoke(self, args, confirm=None):
        with patch("pvecontrol.actions.vm.PVECluster.create_from_config", return_value=self.cluster):
            obj = {"args": SimpleNamespace(cluster="name", output=OutputFormats.TEXT)}
            return CliRunner().invoke(unlock, args, obj=obj, input=confirm)

    @responses.activate
    def test_unlock(self):
        responses.put(
            "https://host:8006/api2/json/nodes/pve-devel-1/qemu/100/config",
            body=json.dumps({"data": None}),
        )

        result = self._invoke(["100"], confirm="yes\n")

        assert result.exit_code == 0
        # lock details are displayed before asking for confirmation
        assert "Removing lock 'backup' on VM 100 (vm-100)" in result.output
        assert "Lock 'backup' removed from VM 100 (vm-100)" in result.output
        assert len(responses.calls) == 1
        body = responses.calls[0].request.body
        assert "delete=lock" in body
        assert "skiplock=1" in body

    @responses.activate
    def test_unlock_force(self):
        responses.put(
            "https://host:8006/api2/json/nodes/pve-devel-1/qemu/100/config",
            body=json.dumps({"data": None}),
        )

        # no input available, the command must not ask for confirmation
        result = self._invoke(["100", "--force"])

        assert result.exit_code == 0
        assert "Confirm" not in result.output
        assert "Lock 'backup' removed from VM 100 (vm-100)" in result.output
        assert len(responses.calls) == 1

    @responses.activate
    def test_unlock_refused(self):
        result = self._invoke(["100"], confirm="no\n")

        assert result.exit_code == 0
        assert "Removing lock 'backup' on VM 100 (vm-100)" in result.output
        assert "Aborting" in result.output
        assert len(responses.calls) == 0

    @responses.activate
    def test_unlock_not_locked(self):
        result = self._invoke(["101"])

        assert result.exit_code == 0
        assert "VM 101 (vm-101) is not locked" in result.output
        assert len(responses.calls) == 0

    @responses.activate
    def test_unlock_unknown_vm(self):
        result = self._invoke(["999"])

        assert result.exit_code == 1
        assert "Vm to unlock not found" in result.output
        assert len(responses.calls) == 0

    @responses.activate
    def test_unlock_dry_run(self):
        result = self._invoke(["100", "--dry-run"], confirm="yes\n")

        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert len(responses.calls) == 0


class PVEVmActionsTestcase(PVEControlTestcase):

    def _post_setup(self):
        super()._post_setup()
        self.vm = self.cluster.vms[0]
        self.vm._api = MagicMock()  # pylint: disable=protected-access

    def test_start(self):
        self.vm.start()
        self.vm._api.nodes.assert_called_with(self.vm.node)  # pylint: disable=protected-access
        self.vm._api.nodes(self.vm.node).qemu.assert_called_with(self.vm.vmid)  # pylint: disable=protected-access
        self.vm._api.nodes(self.vm.node).qemu(  # pylint: disable=protected-access
            self.vm.vmid
        ).status.start.post.assert_called_once_with()

    def test_shutdown(self):
        self.vm.shutdown()
        self.vm._api.nodes(self.vm.node).qemu(  # pylint: disable=protected-access
            self.vm.vmid
        ).status.shutdown.post.assert_called_once_with()

    def test_shutdown_with_timeout(self):
        self.vm.shutdown(timeout=42)
        self.vm._api.nodes(self.vm.node).qemu(  # pylint: disable=protected-access
            self.vm.vmid
        ).status.shutdown.post.assert_called_once_with(timeout=42)

    def test_stop(self):
        self.vm.stop()
        self.vm._api.nodes(self.vm.node).qemu(  # pylint: disable=protected-access
            self.vm.vmid
        ).status.stop.post.assert_called_once_with()

    def test_stop_overrule_shutdown(self):
        self.vm.stop(overrule_shutdown=True)
        self.vm._api.nodes(self.vm.node).qemu(  # pylint: disable=protected-access
            self.vm.vmid
        ).status.stop.post.assert_called_once_with(**{"overrule-shutdown": 1})


class PVEVmCliActionsTestcase(PVEControlTestcase):
    """Already-running / already-stopped VM should be a no-op, without calling the Proxmox API"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.vms.append(fake_vm(105, self.nodes[1], status="stopped"))

    @patch("pvecontrol.actions.vm.PVECluster.create_from_config")
    def test_start_already_running(self, mock_create):
        mock_create.return_value = self.cluster
        with self.assertLogs(level="WARNING") as logs:
            result = CliRunner().invoke(pvecontrol, ["-c", "name", "vm", "start", "100"])
        assert result.exit_code == 0
        assert "already running" in "\n".join(logs.output)

    @patch("pvecontrol.actions.vm.PVECluster.create_from_config")
    def test_shutdown_already_stopped(self, mock_create):
        mock_create.return_value = self.cluster
        with self.assertLogs(level="WARNING") as logs:
            result = CliRunner().invoke(pvecontrol, ["-c", "name", "vm", "shutdown", "105"])
        assert result.exit_code == 0
        assert "already stopped" in "\n".join(logs.output)

    @patch("pvecontrol.actions.vm.PVECluster.create_from_config")
    def test_stop_already_stopped(self, mock_create):
        mock_create.return_value = self.cluster
        with self.assertLogs(level="WARNING") as logs:
            result = CliRunner().invoke(pvecontrol, ["-c", "name", "vm", "stop", "105"])
        assert result.exit_code == 0
        assert "already stopped" in "\n".join(logs.output)


class PVEVmConfirmationTestcase(PVEControlTestcase):
    """vm start/shutdown/stop must not act without --force or explicit user confirmation"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.vms.append(fake_vm(105, self.nodes[1], status="stopped"))

    def _post_setup(self):
        super()._post_setup()
        self.cluster.refresh = MagicMock()

    def _run(self, args, **kwargs):
        with patch("pvecontrol.actions.vm.PVECluster.create_from_config", return_value=self.cluster), patch(
            "pvecontrol.actions.vm.print_task"
        ) as mock_print_task:
            result = CliRunner().invoke(pvecontrol, ["-c", "name", *args], **kwargs)
        return result, mock_print_task

    def test_start_dry_run_does_not_execute(self):
        vm = self.cluster.get_vm(105)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "start", "105", "--dry-run"], input="yes\n")

        assert result.exit_code == 0
        assert "Dry run" in result.output
        vm._api.nodes.assert_not_called()  # pylint: disable=protected-access
        mock_print_task.assert_not_called()

    def test_start_force_executes_without_prompting(self):
        vm = self.cluster.get_vm(105)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "start", "105", "--force"])

        assert result.exit_code == 0
        assert "Confirm" not in result.output
        vm._api.nodes(vm.node).qemu(  # pylint: disable=protected-access
            vm.vmid
        ).status.start.post.assert_called_once_with()
        mock_print_task.assert_called_once()

    def test_start_confirmed_executes(self):
        vm = self.cluster.get_vm(105)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "start", "105"], input="yes\n")

        assert result.exit_code == 0
        vm._api.nodes(vm.node).qemu(  # pylint: disable=protected-access
            vm.vmid
        ).status.start.post.assert_called_once_with()
        mock_print_task.assert_called_once()

    def test_start_declined_does_not_execute(self):
        vm = self.cluster.get_vm(105)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "start", "105"], input="no\n")

        assert result.exit_code == 0
        assert "Aborting" in result.output
        vm._api.nodes.assert_not_called()  # pylint: disable=protected-access
        mock_print_task.assert_not_called()

    def test_shutdown_dry_run_does_not_execute(self):
        vm = self.cluster.get_vm(100)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "shutdown", "100", "--dry-run"], input="yes\n")

        assert result.exit_code == 0
        assert "Dry run" in result.output
        vm._api.nodes.assert_not_called()  # pylint: disable=protected-access
        mock_print_task.assert_not_called()

    def test_shutdown_force_executes_without_prompting(self):
        vm = self.cluster.get_vm(100)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "shutdown", "100", "--force"])

        assert result.exit_code == 0
        vm._api.nodes(vm.node).qemu(  # pylint: disable=protected-access
            vm.vmid
        ).status.shutdown.post.assert_called_once_with()
        mock_print_task.assert_called_once()

    def test_stop_dry_run_does_not_execute(self):
        vm = self.cluster.get_vm(100)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "stop", "100", "--dry-run"], input="yes\n")

        assert result.exit_code == 0
        assert "Dry run" in result.output
        vm._api.nodes.assert_not_called()  # pylint: disable=protected-access
        mock_print_task.assert_not_called()

    def test_stop_force_executes_without_prompting(self):
        vm = self.cluster.get_vm(100)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "stop", "100", "--force"])

        assert result.exit_code == 0
        vm._api.nodes(vm.node).qemu(  # pylint: disable=protected-access
            vm.vmid
        ).status.stop.post.assert_called_once_with()
        mock_print_task.assert_called_once()

    def test_stop_overrule_shutdown_executes(self):
        vm = self.cluster.get_vm(100)
        vm._api = MagicMock()  # pylint: disable=protected-access

        result, mock_print_task = self._run(["vm", "stop", "100", "--force", "--overrule-shutdown"])

        assert result.exit_code == 0
        vm._api.nodes(vm.node).qemu(  # pylint: disable=protected-access
            vm.vmid
        ).status.stop.post.assert_called_once_with(**{"overrule-shutdown": 1})
        mock_print_task.assert_called_once()
