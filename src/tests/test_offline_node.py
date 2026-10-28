import io
import contextlib
import re

from datetime import datetime, timedelta
from unittest.mock import patch

import responses

from click.testing import CliRunner

from pvecontrol import pvecontrol
from pvecontrol.actions.report import _build_report_data
from pvecontrol.models.node import NodeStatus
from pvecontrol.models.task import TaskRunningStatus
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
        self.backup_jobs = [fake_backup_job(1, "300")]
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

    def test_check_nodes(self):
        assert self._messages("nodes", CheckCode.CRIT) == [f"Node '{OFFLINE_NODE}' is offline"]
        assert not any(OFFLINE_NODE in m.message for m in self.checks["nodes"].messages if m.code == CheckCode.OK)

    def test_check_ha_vms(self):
        warnings = self._messages("ha_vms", CheckCode.WARN)
        assert f"Node '{OFFLINE_NODE}' has VM 300 that can't be checked, the node is not online" in warnings
        assert "HA resource 'vm:999' has no matching VM" in warnings

    def test_checks_skip_offline_node(self):
        for check_id in ["vms_start_on_boot", "disk_unused"]:
            for m in self.checks[check_id].messages:
                assert OFFLINE_NODE not in m.message and not re.search(r"\b30[01]\b", m.message), m.message

    def test_report(self):
        nodes = {n["node"]: n for n in self.report["nodes"]}
        assert nodes[OFFLINE_NODE]["version"] == ""
        assert nodes[OFFLINE_NODE]["vms"] == 2
        assert nodes["pve-devel-1"]["version"] == "9.1.4"

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
