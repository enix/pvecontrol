import logging

from unittest.mock import MagicMock, patch

import proxmoxer.core

from click.testing import CliRunner

from pvecontrol import pvecontrol
from pvecontrol.models.task import PVETask
from pvecontrol.models.vm import PVEVm
from tests.testcase import PVEControlTestcase
from tests.fixtures.api import fake_vm

UPID = "UPID:pve-devel-1:00001234:00005678:6AE38CD2:qmstart:100:root@pam:"


def fake_task(exitstatus):
    """A task as listed by cluster/tasks: a finished one has an exit status and an endtime, a running one neither"""
    return PVETask(None, UPID, summary={} if exitstatus is None else {"endtime": 1, "status": exitstatus})


class PVEVmErrorsTestcase(PVEControlTestcase):
    """Errors of the vm and task commands go to the logs (stderr) and end with exit code 1"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.vms.append(fake_vm(105, self.nodes[1], status="stopped"))

    def _post_setup(self):
        super()._post_setup()
        self.cluster.refresh = MagicMock()

    def _run(self, args, task=None, module="vm", **kwargs):
        with (
            patch(f"pvecontrol.actions.{module}.PVECluster.create_from_config", return_value=self.cluster),
            patch(f"pvecontrol.actions.{module}.print_task", return_value=task) as mock_print_task,
            self.assertLogs(level="DEBUG") as logs,
        ):
            result = CliRunner().invoke(pvecontrol, ["-c", "name", *args], **kwargs)
        errors = [record.getMessage() for record in logs.records if record.levelno >= logging.ERROR]
        return result, errors, mock_print_task

    def _mock_api(self, vmid):
        vm = self.cluster.get_vm(vmid)
        vm._api = MagicMock()  # pylint: disable=protected-access
        return vm._api.nodes(vm.node).qemu(vm.vmid)  # pylint: disable=protected-access

    def test_not_found_errors_are_logged(self):
        cases = [
            (["vm", "migrate", "999", "--target", "pve-devel-2"], "Source VM 999 not found"),
            (["vm", "migrate", "100", "--target", "pve-unknown"], "Target node pve-unknown does not exist"),
            (["vm", "start", "999"], "VM 999 not found"),
            (["vm", "shutdown", "999"], "VM 999 not found"),
            (["vm", "stop", "999"], "VM 999 not found"),
        ]
        for args, message in cases:
            with self.subTest(args=args):
                result, errors, _ = self._run(args)
                assert result.exit_code == 1
                assert errors == [message]
                assert result.stdout == ""

    def test_declined_confirmation_exits_in_error(self):
        for args in [["vm", "start", "105"], ["vm", "shutdown", "100"], ["vm", "stop", "100"]]:
            with self.subTest(args=args):
                api = self._mock_api(int(args[2]))
                result, errors, mock_print_task = self._run(args, input="no\n")
                assert result.exit_code == 1
                assert errors == ["Aborting"]
                assert "Aborting" not in result.stdout
                assert not api.mock_calls
                mock_print_task.assert_not_called()

    def test_failed_task_exits_in_error_when_waited_for(self):
        for option in ["--wait", "--follow"]:
            for args in [["vm", "start", "105"], ["vm", "shutdown", "100"], ["vm", "stop", "100"]]:
                with self.subTest(args=args, option=option):
                    self._mock_api(int(args[2]))
                    result, errors, _ = self._run([*args, "--force", option], task=fake_task("start failed"))
                    assert result.exit_code == 1
                    assert errors == [f"Task {UPID} failed: start failed"]

    def test_failed_migration_exits_in_error_when_waited_for(self):
        api = self._mock_api(100)
        api.migrate.get.return_value = {"local_disks": []}
        result, errors, _ = self._run(
            ["vm", "migrate", "100", "--target", "pve-devel-2", "--wait"], task=fake_task("migration aborted")
        )
        assert result.exit_code == 1
        assert errors == [f"Task {UPID} failed: migration aborted"]

    def test_failed_restore_exits_in_error_when_waited_for(self):
        with patch.object(PVEVm, "create", return_value=UPID):
            result, errors, _ = self._run(
                ["vm", "restore", "200", "--target", "pve-devel-1", "--archive", "s3:backup/x", "--wait"],
                task=fake_task("restore failed"),
            )
        assert result.exit_code == 1
        assert errors == [f"Task {UPID} failed: restore failed"]

    def test_task_result_ignored_without_wait(self):
        # The task is usually still running, and nobody asked to wait for its result anyway
        for exitstatus in [None, "start failed"]:
            with self.subTest(exitstatus=exitstatus):
                self._mock_api(105)
                result, errors, _ = self._run(["vm", "start", "105", "--force"], task=fake_task(exitstatus))
                assert result.exit_code == 0
                assert not errors

    def test_successful_task_waited_for(self):
        self._mock_api(105)
        result, errors, _ = self._run(["vm", "start", "105", "--force", "--wait"], task=fake_task("OK"))
        assert result.exit_code == 0
        assert not errors

    def test_api_errors_are_logged(self):
        cases = [
            (["vm", "start", "105", "--force"], "status.start.post", "Error starting VM 105"),
            (["vm", "shutdown", "100", "--force"], "status.shutdown.post", "Error shutting down VM 100"),
            (["vm", "stop", "100", "--force"], "status.stop.post", "Error stopping VM 100"),
            (["vm", "migrate", "100", "--target", "pve-devel-2"], "migrate.get", "Error migrating VM 100"),
            (["vm", "migrate", "100", "--target", "pve-devel-2"], "migrate.post", "Error migrating VM 100"),
        ]
        for args, call, message in cases:
            with self.subTest(args=args, call=call):
                api = self._mock_api(int(args[2]))
                api.migrate.get.return_value = {"local_disks": []}
                endpoint = api
                for attribute in call.split("."):
                    endpoint = getattr(endpoint, attribute)
                endpoint.side_effect = proxmoxer.core.ResourceException(500, "Internal Server Error", "boom")
                result, errors, mock_print_task = self._run(args)
                assert result.exit_code == 1
                assert len(errors) == 1
                assert errors[0].startswith(message)
                assert "boom" in errors[0]
                mock_print_task.assert_not_called()

    def test_task_get_failed_task(self):
        for options, exit_code in [([], 0), (["--wait"], 1), (["--follow"], 1)]:
            with self.subTest(options=options):
                result, errors, _ = self._run(["task", "get", UPID, *options], task=fake_task("failed"), module="task")
                assert result.exit_code == exit_code
                assert errors == ([f"Task {UPID} failed: failed"] if exit_code else [])


def test_task_failed():
    assert fake_task("migration aborted").failed()
    assert not fake_task("OK").failed()
    # A running task has no result yet, nor has one whose node can't be reached
    assert not fake_task(None).failed()
    assert not PVETask(None, UPID, summary={}, node_online=False).failed()
