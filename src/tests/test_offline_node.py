import io
import contextlib
import json
import re
import unittest

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import requests
import responses

from proxmoxer.core import ResourceException

from click.testing import CliRunner

from pvecontrol import pvecontrol
from pvecontrol.actions.report import _build_report_data
from pvecontrol.models.node import NodeStatus, PVENode
from pvecontrol.models.storage import PVEStorage
from pvecontrol.models.task import PVETask, TaskRunningStatus
from pvecontrol.models.vm import VmStatus
from pvecontrol.sanitycheck.checks import CheckCode
from pvecontrol.sanitycheck.tests import DEFAULT_CHECKS
from pvecontrol.utils import print_task
from tests.fixtures.api import (
    fake_backup,
    fake_backup_job,
    fake_ha_resource,
    fake_ha_rule,
    fake_node,
    fake_offline_vm,
    fake_storage_resource,
    fake_vm,
)
from tests.testcase import PVEControlTestcase

OFFLINE_NODE = "pve-devel-3"
NO_ROUTE = ResourceException(595, "Errors during connection establishment, proxy handshake", "No route to host")
UPID_ONLINE = "UPID:pve-devel-1:00030925:03AF335A:6AE1F6B4:qmstart:100:root@pam:"
UPID_OFFLINE_DONE = "UPID:pve-devel-3:0003092A:03AF3363:6AE1F6B5:qmshutdown:300:root@pam:"
UPID_OFFLINE_RUNNING = "UPID:pve-devel-3:0003092B:03AF3364:6AE1F6B6:vzdump:301:root@pam:"


class OfflineNodeTestcase(PVEControlTestcase):
    """pve-devel-3 is powered off. cluster/resources and cluster/tasks keep listing its VMs, storages and tasks,
    but every API call proxied to it would fail (HTTP 595) or hang until the timeout."""

    def _build_fixtures(self):
        self.backups = [
            fake_backup("s3", 100, datetime.now() - timedelta(minutes=10)),
            fake_backup("s3", 300, datetime.now() - timedelta(minutes=1000)),
        ]
        super()._build_fixtures()
        self.nodes[2] = fake_node(3, online=False)
        self.vms += [
            # Shortly after the node went down, cluster/resources keeps the last known state of its VMs
            fake_vm(300, self.nodes[2], status="running"),
            # Later on, only the id, node and an unknown status remain
            fake_offline_vm(301, self.nodes[2]),
        ]
        # vm 300 has an old backup, vm 301 none that can be seen
        self.backup_jobs = [fake_backup_job(1, "300"), fake_backup_job(2, "301")]
        # The offline node comes first for the shared storage, backups must be listed through another node
        self.storage_resources = [
            fake_storage_resource("s3", OFFLINE_NODE),
            fake_storage_resource("s3", "pve-devel-1"),
            fake_storage_resource("s3", "pve-devel-2"),
            fake_storage_resource("local", OFFLINE_NODE, shared=0, plugin_type="dir"),
        ]
        self.storages_contents = {n["status"]["name"]: {"s3": self.backups, "local": []} for n in self.nodes}
        self.ha_rules = [fake_ha_rule("ha-all", ["pve-devel-1", "pve-devel-2", OFFLINE_NODE], [100, 300])]
        self.ha_resources = [fake_ha_resource(100), fake_ha_resource(300), fake_ha_resource(999)]

    def _cluster_config(self):
        return {"node": {"cpufactor": 2.5, "memoryminimum": 0}, "vm": {"max_last_backup": 100}}

    def _register_routes(self):
        super()._register_routes()
        self.responses_get(
            "/api2/json/cluster/tasks",
            data=[
                {"upid": UPID_ONLINE, "node": "pve-devel-1", "starttime": 1793193652},
                {
                    "upid": UPID_OFFLINE_DONE,
                    "node": OFFLINE_NODE,
                    "starttime": 1793193653,
                    "endtime": 1793193656,
                    "status": "OK",
                },
                {"upid": UPID_OFFLINE_RUNNING, "node": OFFLINE_NODE, "starttime": 1793193654},
            ],
        )
        self.responses_get(
            f"/api2/json/nodes/pve-devel-1/tasks/{UPID_ONLINE}/status",
            data={"status": "running"},
        )
        for node in ["pve-devel-1", "pve-devel-2"]:
            self.responses_get(f"/api2/json/nodes/{node}/storage/local/content", params={"content": "images"})

    def _post_setup(self):
        _ = self.cluster.ha
        self.tasks = self.cluster.tasks
        self.backups_found = self.cluster.backups
        # Before the report, which flattens the storage objects
        self.grouped_storages = [
            {
                "storage": item["storage"].storage,
                "node": item["storage"].node,
                "nodes": item["nodes"],
                "usage": item["usage"],
            }
            for item in PVEStorage.get_grouped_list(self.cluster)
        ]
        self.checks = {}
        for check_id, check_class in DEFAULT_CHECKS.items():
            self.checks[check_id] = check_class(self.cluster)
            self.checks[check_id].run()
        with contextlib.redirect_stdout(io.StringIO()):
            self.report = _build_report_data(self.cluster)
            print_task(self.cluster, UPID_OFFLINE_DONE)
        # Every route is registered for every node, so a call to the offline node would not fail here: track them
        self.offline_calls = [c.request.url for c in responses.calls if f"/nodes/{OFFLINE_NODE}/" in c.request.url]

    def _messages(self, check_id, code):
        return [m.message for m in self.checks[check_id].messages if m.code == code]

    def test_no_api_call_to_offline_node(self):
        assert not self.offline_calls

    def test_node(self):
        node = self.cluster.find_node(OFFLINE_NODE)
        assert node.status == NodeStatus.OFFLINE
        assert not node.online
        assert node.version == {}
        assert not self.cluster.is_node_online(OFFLINE_NODE)
        assert self.cluster.is_node_online("pve-devel-1")
        assert not self.cluster.is_node_online("unknown-node")

    def test_vms_listed_with_unknown_status(self):
        node = self.cluster.find_node(OFFLINE_NODE)
        assert sorted(vm.vmid for vm in node.vms) == [300, 301]
        assert all(vm.status == VmStatus.UNKNOWN for vm in node.vms)
        # The stale "running" status of vm 300 must not count as allocated resources
        assert node.allocatedcpu == 0
        assert node.allocatedmem == 0
        assert self.cluster.get_vm(300).node == OFFLINE_NODE
        assert self.cluster.get_vm(999) is None

    def test_tasks(self):
        tasks = {t.upid: t for t in self.tasks}
        assert tasks[UPID_ONLINE].runningstatus == TaskRunningStatus.RUNNING
        assert tasks[UPID_OFFLINE_DONE].runningstatus == TaskRunningStatus.STOPPED
        assert tasks[UPID_OFFLINE_DONE].exitstatus == "OK"
        assert tasks[UPID_OFFLINE_DONE].endtime == 1793193656
        assert tasks[UPID_OFFLINE_RUNNING].runningstatus == TaskRunningStatus.UNKNOWN

    def test_backups_listed_through_an_online_node(self):
        assert sorted(b.vmid for b in self.backups_found) == [100, 300]

    def test_check_vm_backups(self):
        # Recent backups of vm 300 may sit on a local storage of its node: an old one is not a proof
        assert not self._messages("vm_backups", CheckCode.CRIT)
        warnings = self._messages("vm_backups", CheckCode.WARN)
        assert any("Vm 300" in m and f"node '{OFFLINE_NODE}' is not online" in m for m in warnings)

    def test_check_vm_backups_none_found(self):
        warnings = self._messages("vm_backups", CheckCode.WARN)
        assert any("Vm 301" in m and "no backup found" in m and OFFLINE_NODE in m for m in warnings)
        assert not any("Vm 301" in m and "never been backed up" in m for m in warnings)

    def test_metrics_exclude_offline_node(self):
        # The offline node keeps its maxcpu and maxmem in cluster/resources shortly after going down
        assert self.cluster.cpu_metrics["total"] == 2 * 32
        assert self.cluster.memory_metrics["total"] == 2 * 202758361088
        # Only the s3 entries of the 2 online nodes count, not the offline node's s3 and local storages
        assert self.cluster.disk_metrics["total"] == 2 * 33601372160
        # Building the storage objects left the cluster/resources entries intact
        assert all("node" in storage for storage in self.cluster.resources_storages)

    def test_storage_without_online_entry_is_unknown(self):
        local = [item for item in self.grouped_storages if item["storage"] == "local"]
        assert [item["usage"] for item in local] == ["unknown"]
        rows = [row for row in self.report["storages"] if row["storage"] == "local"]
        assert [(row["usage"], row["status"]) for row in rows] == [("unknown", "unknown")]
        # A shared storage with an online entry keeps its usage
        s3 = [item for item in self.grouped_storages if item["storage"] == "s3"]
        assert s3[0]["usage"] != "unknown"

    def test_check_nodes(self):
        assert self._messages("nodes", CheckCode.CRIT) == [f"Node '{OFFLINE_NODE}' is offline"]
        assert not any(OFFLINE_NODE in m.message for m in self.checks["nodes"].messages if m.code == CheckCode.OK)

    def test_check_ha_vms(self):
        warnings = self._messages("ha_vms", CheckCode.WARN)
        assert f"Node '{OFFLINE_NODE}' has VM 300 that can't be checked, the node is not online" in warnings
        assert "HA resource 'vm:999' has no matching VM" in warnings

    def test_checks_skip_offline_node(self):
        # Each check warns about what it skipped, it may run without the nodes check
        expected = {
            "vms_start_on_boot": f"Node '{OFFLINE_NODE}' is not online, 2 VM(s) on it can't be checked",
            "disk_unused": f"Node '{OFFLINE_NODE}' is not online, 2 VM(s) and 1 storage(s) on it can't be checked",
        }
        for check_id, warning in expected.items():
            assert warning in self._messages(check_id, CheckCode.WARN)
            for m in self.checks[check_id].messages:
                if m.message != warning:
                    assert OFFLINE_NODE not in m.message and not re.search(r"\b30[01]\b", m.message), m.message

    def test_report(self):
        nodes = {n["node"]: n for n in self.report["nodes"]}
        assert nodes[OFFLINE_NODE]["version"] == ""
        assert nodes[OFFLINE_NODE]["vms"] == 2
        assert nodes["pve-devel-1"]["version"] == "9.1.4"
        summary = self.report["vm_summary"][0]
        assert (summary["running"], summary["stopped"], summary["unknown"], summary["other"]) == (5, 0, 2, 0)

    def test_shared_storage_represented_by_an_online_node(self):
        # The s3 entry of the offline node comes first in cluster/resources
        s3 = [item for item in self.grouped_storages if item["storage"] == "s3"]
        assert len(s3) == 1
        assert s3[0]["node"] == "pve-devel-1"
        assert s3[0]["nodes"] == [OFFLINE_NODE, "pve-devel-1", "pve-devel-2"]

    def test_task_wait_refused(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertLogs(level="ERROR") as logs:
            with self.assertRaises(SystemExit) as exit_info:
                print_task(self.cluster, UPID_OFFLINE_RUNNING, wait=True)
        assert exit_info.exception.code == 1
        assert f"node {OFFLINE_NODE} can't be reached" in "\n".join(logs.output)
        # A finished task needs no waiting
        with contextlib.redirect_stdout(io.StringIO()):
            print_task(self.cluster, UPID_OFFLINE_DONE, wait=True)

    def test_vm_actions_refused(self):
        for args in [
            ["vm", "start", "301", "--force"],
            ["vm", "stop", "300", "--force"],
            ["vm", "shutdown", "300", "--force"],
            ["vm", "unlock", "300", "--force"],
            ["vm", "migrate", "300", "--target", "pve-devel-1"],
        ]:
            with patch("pvecontrol.actions.vm.PVECluster.create_from_config", return_value=self.cluster):
                with self.assertLogs(level="ERROR") as logs:
                    result = CliRunner().invoke(pvecontrol, ["-c", "name", *args])
            assert result.exit_code == 1, args
            assert f"is on node {OFFLINE_NODE}, which is not online" in "\n".join(logs.output), args

    def test_vm_actions_to_offline_target_refused(self):
        for args, error in [
            (["vm", "migrate", "100", "--target", OFFLINE_NODE], f"Target node {OFFLINE_NODE} is not online"),
            (
                ["vm", "restore", "999", "--target", OFFLINE_NODE, "--archive", "s3:backup/vzdump.vma.zst"],
                f"Target node {OFFLINE_NODE} does not exist or is not online",
            ),
        ]:
            with patch("pvecontrol.actions.vm.PVECluster.create_from_config", return_value=self.cluster):
                with self.assertLogs(level="ERROR") as logs:
                    result = CliRunner().invoke(pvecontrol, ["-c", "name", *args])
            assert result.exit_code == 1, args
            assert error in "\n".join(logs.output), args


class TaskNodeLostTestcase(unittest.TestCase):
    """The node of a task stops answering while pvecontrol waits for it"""

    def _task(self, status_error=NO_ROUTE, log_side_effect=None):
        api = MagicMock()
        api.nodes.return_value.tasks.return_value.status.get.side_effect = [{"status": "running"}, status_error]
        api.nodes.return_value.tasks.return_value.log.get.side_effect = log_side_effect
        api.nodes.return_value.tasks.return_value.log.get.return_value = []
        task = PVETask(api, UPID_ONLINE)
        task.log_get = api.nodes.return_value.tasks.return_value.log.get
        return task

    def test_refresh_marks_task_unknown(self):
        # HTTP 595 from the API, or a network partition between pvecontrol and the API
        for error in [NO_ROUTE, requests.exceptions.ConnectTimeout("timed out")]:
            task = self._task(status_error=error)
            assert task.running()
            task.refresh()
            assert task.unknown(), error

    def test_log_failure_keeps_status(self):
        task = self._task(log_side_effect=NO_ROUTE)
        with self.assertLogs(level="WARNING") as logs:
            assert task.log() == []
        assert "Can't read the log of task" in "\n".join(logs.output)
        # The status read before still stands, and the node is not asked for the log again
        assert task.running()
        assert task.log() == []
        assert task.log_get.call_count == 1

    def test_log_other_errors_are_raised(self):
        task = self._task(log_side_effect=ResourceException(500, "Internal Server Error", "boom"))
        with self.assertRaises(ResourceException):
            task.log()

    def test_wait_stops_and_fails(self):
        for options, task_args in [
            ({"wait": True}, {}),
            ({"follow": True}, {}),
        ]:
            task = self._task(**task_args)
            proxmox = MagicMock()
            proxmox.get_task.return_value = task
            proxmox.is_node_online.return_value = True
            with patch("pvecontrol.utils.time.sleep"), contextlib.redirect_stdout(io.StringIO()):
                with self.assertLogs(level="ERROR") as logs, self.assertRaises(SystemExit) as exit_info:
                    print_task(proxmox, UPID_ONLINE, **options)
            assert exit_info.exception.code == 1, options
            assert "Lost track of task" in "\n".join(logs.output), options

    def _print_task(self, task, **options):
        proxmox = MagicMock()
        proxmox.get_task.return_value = task
        proxmox.find_task.return_value = task
        proxmox.is_node_online.return_value = True
        with patch("pvecontrol.utils.time.sleep"), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertLogs(level="WARNING") as logs:
                print_task(proxmox, UPID_ONLINE, **options)
        return output.getvalue(), "\n".join(logs.output)

    def test_log_unavailable_on_finished_task(self):
        # task get on a finished task: its result is known even if its log can't be read
        task = self._task(log_side_effect=NO_ROUTE)
        task.runningstatus = TaskRunningStatus.STOPPED
        output, logs = self._print_task(task)
        assert "TaskRunningStatus.STOPPED" in output
        assert "Can't read the log of task" in logs
        assert task.log_get.call_count == 1

    def test_follow_without_log_still_waits_for_the_result(self):
        # The node stops answering for the log only: the status is still polled until the task ends
        task = self._task(status_error={"status": "stopped", "exitstatus": "OK"}, log_side_effect=NO_ROUTE)
        output, _ = self._print_task(task, follow=True)
        assert "TaskRunningStatus.STOPPED" in output
        assert task.log_get.call_count == 1


class RebootingNodeTestcase(PVEControlTestcase):
    """pve-devel-2 reboots: cluster/resources still lists it online, but its API refuses connections.
    Captured on PVE 9.2 for about 3 s while shutting down, and 2 s while booting."""

    error = {"status": 595, "body": json.dumps({"data": None})}

    def _cluster_config(self):
        return {"node": {"cpufactor": 2.5, "memoryminimum": 0}, "vm": {"max_last_backup": 100}}

    def _register_routes(self):
        # Registered first, so the version call of pve-devel-2 gets it instead of the default answer
        responses.get("https://host:8006/api2/json/nodes/pve-devel-2/version", **self.error)
        super()._register_routes()

    def _post_setup(self):
        _ = self.cluster.ha
        self.checks = {check_id: check_class(self.cluster) for check_id, check_class in DEFAULT_CHECKS.items()}
        for check in self.checks.values():
            check.run()
        self.node_calls = [c.request.url for c in responses.calls if "/nodes/pve-devel-2/" in c.request.url]

    def test_node_handled_as_unknown(self):
        node = self.cluster.find_node("pve-devel-2")
        assert node.status == NodeStatus.UNKNOWN
        assert not self.cluster.is_node_online("pve-devel-2")
        assert node.version == {}
        assert all(vm.status == VmStatus.UNKNOWN for vm in node.vms)
        assert self.cluster.is_node_online("pve-devel-1")

    def test_only_the_version_call_reaches_the_node(self):
        assert [url.split("/api2/json")[1] for url in self.node_calls] == ["/nodes/pve-devel-2/version"]

    def test_check_nodes(self):
        crit = [m.message for m in self.checks["nodes"].messages if m.code == CheckCode.CRIT]
        assert crit == ["Node 'pve-devel-2' is unknown"]


class RebootingNodeTimeoutTestcase(RebootingNodeTestcase):
    """Between both windows, the call proxied to the rebooting node can also hang until the timeout"""

    error = {"body": requests.exceptions.ReadTimeout("Read timed out")}


class NodeVersionOtherErrorTestcase(unittest.TestCase):
    def test_other_errors_are_raised(self):
        cluster = MagicMock()
        cluster.api.nodes.return_value.version.get.side_effect = ResourceException(403, "Forbidden", "no access")
        with self.assertRaises(ResourceException):
            PVENode(cluster, "pve-devel-1", "online")
