import itertools
import json
import re

from unittest.mock import patch
from urllib.parse import parse_qs

import responses

from pvecontrol.models.node import NodeStatus
from tests.fixtures.api import fake_ha_manager_status
from tests.testcase import PVEControlTestcase

API = "https://host:8006/api2/json"
MANAGER_STATUS_URL = f"{API}/cluster/ha/status/manager_status"
CURRENT_URL = f"{API}/cluster/ha/status/current"
HA_STATUS_URL = f"{API}/cluster/ha/status"
MAINTENANCE_URL = re.compile(rf"{API}/nodes/[^/]+/maintenance")
HA_COMMAND_URL = re.compile(rf"{API}/cluster/ha/status/(dis)?arm-ha")
HA_INDEX = [{"name": "current"}, {"name": "manager_status"}, {"name": "disarm-ha"}, {"name": "arm-ha"}]

ONLINE = {"pve-devel-1": "online", "pve-devel-2": "online", "pve-devel-3": "online"}
# PVEControlTestcase: pve-devel-1 hosts VMs 100 and 101, pve-devel-2 hosts VMs 102, 103 and 104
SERVICES = {"vm:100": "pve-devel-1", "vm:102": "pve-devel-2"}
# Once pve-devel-1 is drained, the HA manager has moved VM 100 away
DRAINED = {"vm:100": "pve-devel-2", "vm:102": "pve-devel-2"}


def _status(node_status=None, **kwargs):
    return fake_ha_manager_status(node_status=node_status or ONLINE, service_status=SERVICES, **kwargs)


def _with(node, state, lrm_mode="active", services=None, **kwargs):
    """Manager status where node is in the given HA state, with its LRM in lrm_mode and the given HA resources"""
    status = fake_ha_manager_status(
        node_status={**ONLINE, node: state},
        lrm_modes={node: lrm_mode},
        service_status=SERVICES if services is None else services,
        **kwargs,
    )
    return status


class HaCommandsTestcase(PVEControlTestcase):
    """The API is served by a node running pve-manager 9.2.33, like pve-devel-1 and pve-devel-2, pve-devel-3 runs an
    older version"""

    def _post_setup(self):
        self.cluster.version = {"version": "9.2.33", "release": "9.2"}
        for name in ["pve-devel-1", "pve-devel-2"]:
            self.cluster.find_node(name).version = {"version": "9.2.33", "release": "9.2"}

    def _reset_ha(self):
        # pylint: disable=protected-access
        self.cluster._ha_manager_status = None
        self.cluster._node_ha_states = None

    # pylint: disable=too-many-arguments
    def _run(self, args, statuses, current=None, ha_index=None, put_status=200, post_status=200, answer=None):
        """Run the command, the HA manager status going through statuses at each refresh (an int is an HTTP error)"""
        responses.reset()
        self._reset_ha()
        for status in statuses:
            if isinstance(status, int):
                responses.get(MANAGER_STATUS_URL, status=status, body=json.dumps({"data": None}))
            else:
                responses.get(MANAGER_STATUS_URL, body=json.dumps({"data": status}))
        if isinstance(current, int):
            responses.get(CURRENT_URL, status=current, body=json.dumps({"data": None}))
        else:
            responses.get(CURRENT_URL, body=json.dumps({"data": current or []}))
        responses.get(HA_STATUS_URL, body=json.dumps({"data": HA_INDEX if ha_index is None else ha_index}))
        responses.put(MAINTENANCE_URL, status=put_status, body=json.dumps({"data": None}))
        responses.post(HA_COMMAND_URL, status=post_status, body=json.dumps({"data": None}))
        with (
            patch("pvecontrol.actions.ha.PVECluster.create_from_config", return_value=self.cluster),
            patch.object(self.cluster, "refresh", side_effect=self._reset_ha),
            patch("pvecontrol.actions.ha.time.sleep"),
        ):
            return self._invoke_logged(args, answer)

    @staticmethod
    def _writes(method):
        return [
            (call.request.url, parse_qs(call.request.body or ""))
            for call in responses.calls
            if call.request.method == method
        ]


class HaStatusTestcase(HaCommandsTestcase):

    @responses.activate
    def test_status_json(self):
        current = [
            {"id": "lrm:pve-devel-2", "type": "lrm", "node": "pve-devel-2", "maintenance-request-queued": 1},
            {"id": "lrm:pve-devel-1", "type": "lrm", "node": "pve-devel-1", "maintenance-request-queued": 0},
        ]
        result = self._run(
            ["-o", "json", "ha", "status"], [_with("pve-devel-3", "maintenance", "maintenance")], current
        )
        assert result.exit_code == 0, result.output
        rows = {row["node"]: row for row in json.loads(result.stdout)}
        assert rows["pve-devel-1"] == {
            "node": "pve-devel-1",
            "ha_state": "online",
            "lrm_mode": "active",
            "request_queued": False,
            "ha_resources": 1,
            "ha_active": 1,
            "other_vms": 1,
        }
        assert rows["pve-devel-2"]["request_queued"] is True
        assert rows["pve-devel-2"]["other_vms"] == 2
        assert rows["pve-devel-3"]["ha_state"] == "maintenance"
        assert rows["pve-devel-3"]["lrm_mode"] == "maintenance"

    @responses.activate
    def test_status_node(self):
        result = self._run(["-o", "json", "ha", "status", "pve-devel-2"], [_status()])
        assert result.exit_code == 0, result.output
        assert [row["node"] for row in json.loads(result.stdout)] == ["pve-devel-2"]

    @responses.activate
    def test_status_without_ha(self):
        result = self._run(["-o", "json", "ha", "status"], [[]])
        assert result.exit_code == 0, result.output
        assert {row["ha_state"] for row in json.loads(result.stdout)} == {"-"}

    @responses.activate
    def test_status_unknown_node(self):
        result = self._run(["ha", "status", "pve-unknown"], [_status()])
        assert result.exit_code == 1
        assert self.errors == ["Node pve-unknown does not exist"]

    @responses.activate
    def test_status_forbidden(self):
        result = self._run(["ha", "status"], [403])
        assert result.exit_code == 1
        assert "requires Sys.Audit on /" in self.errors[0]

    @responses.activate
    def test_status_frozen_resources(self):
        # While HA is disarmed in freeze mode, the resources are frozen: they are still counted on their node, but
        # not as active
        status = _status(disarm={"mode": "freeze", "state": "disarmed"})
        status["manager_status"]["service_status"]["vm:100"]["state"] = "freeze"
        result = self._run(["-o", "json", "ha", "status", "pve-devel-1"], [status])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == [
            {
                "node": "pve-devel-1",
                "ha_state": "online",
                "lrm_mode": "active",
                "request_queued": False,
                "ha_resources": 1,
                "ha_active": 0,
                "other_vms": 1,
            }
        ]

    @responses.activate
    def test_status_disarmed(self):
        result = self._run(["ha", "status"], [_status(disarm={"mode": "freeze", "state": "disarmed"})])
        assert result.exit_code == 0, result.output
        assert self.warnings == ["HA is disarmed, resources are in freeze mode"]

    @responses.activate
    def test_status_queue_unreadable(self):
        # An unknown queue is not an empty one
        result = self._run(["-o", "json", "ha", "status", "pve-devel-1"], [_status()], current=500)
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)[0]["request_queued"] is None
        assert "Cannot read the queued HA maintenance requests" in self.warnings[0]

    @responses.activate
    def test_wait_queue_unreadable(self):
        # The node looks online, but a request may be queued: wait instead of saying there is nothing to wait for
        with patch("pvecontrol.actions.ha.time.monotonic", side_effect=itertools.count(step=10)):
            result = self._run(["ha", "status", "pve-devel-1", "--wait", "--timeout", "15"], [_status()], current=500)
        assert result.exit_code == 1
        assert "Timeout waiting for node pve-devel-1" in self.errors[0]

    @responses.activate
    def test_wait_requires_node(self):
        result = self._run(["ha", "status", "--wait"], [_status()])
        assert result.exit_code == 2
        assert "--wait requires a NODE" in result.output

    @responses.activate
    def test_wait_nothing_pending(self):
        result = self._run(["ha", "status", "pve-devel-1", "--wait"], [_status()])
        assert result.exit_code == 1
        assert "nothing to wait for" in self.errors[0]

    @responses.activate
    def test_wait_until_drained(self):
        statuses = [
            _with("pve-devel-1", "online", node_request=["pve-devel-1"]),
            _with("pve-devel-1", "online", node_request=["pve-devel-1"]),
            _with("pve-devel-1", "maintenance", "maintenance", node_request=["pve-devel-1"]),
            _with("pve-devel-1", "maintenance", "maintenance", services=DRAINED, node_request=["pve-devel-1"]),
        ]
        result = self._run(["-o", "json", "ha", "status", "pve-devel-1", "--wait"], statuses)
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)[0]["ha_state"] == "maintenance"
        assert json.loads(result.stdout)[0]["ha_active"] == 0

    @responses.activate
    def test_wait_until_left(self):
        # The CRM dropped the request: the node stays in maintenance until its LRM is active again
        statuses = [
            _with("pve-devel-1", "maintenance", "maintenance", services=DRAINED),
            _with("pve-devel-1", "maintenance", "active", services=DRAINED),
            _with("pve-devel-1", "online", services=DRAINED),
        ]
        result = self._run(["-o", "json", "ha", "status", "pve-devel-1", "--wait"], statuses)
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)[0]["ha_state"] == "online"

    @responses.activate
    def test_wait_ends_in_another_state(self):
        statuses = [
            _with("pve-devel-1", "online", node_request=["pve-devel-1"]),
            _with("pve-devel-1", "unknown", node_request=["pve-devel-1"]),
        ]
        result = self._run(["ha", "status", "pve-devel-1", "--wait"], statuses)
        assert result.exit_code == 1
        assert self.errors == ["Node pve-devel-1 ended in HA state unknown, not in maintenance nor online"]

    @responses.activate
    def test_wait_retries_a_failed_read(self):
        statuses = [
            _with("pve-devel-1", "online", node_request=["pve-devel-1"]),
            500,
            _with("pve-devel-1", "maintenance", "maintenance", services=DRAINED, node_request=["pve-devel-1"]),
        ]
        result = self._run(["ha", "status", "pve-devel-1", "--wait"], statuses)
        assert result.exit_code == 0, result.output
        assert any("retrying" in msg for msg in self.warnings)

    @responses.activate
    def test_wait_sleep_stops_at_the_deadline(self):
        statuses = [_with("pve-devel-1", "online", node_request=["pve-devel-1"])]
        with (
            patch("pvecontrol.actions.ha.time.monotonic", side_effect=itertools.count(step=1)),
            patch("pvecontrol.actions.ha.time.sleep") as sleep,
        ):
            result = self._run(["ha", "status", "pve-devel-1", "--wait", "--timeout", "3"], statuses)
        assert result.exit_code == 1
        assert all(call.args[0] < 10 for call in sleep.call_args_list)

    @responses.activate
    def test_wait_timeout(self):
        statuses = [_with("pve-devel-1", "online", node_request=["pve-devel-1"])]
        with patch("pvecontrol.actions.ha.time.monotonic", side_effect=itertools.count(step=10)):
            result = self._run(["ha", "status", "pve-devel-1", "--wait", "--timeout", "15"], statuses)
        assert result.exit_code == 1
        assert "Timeout waiting for node pve-devel-1" in self.errors[0]

    @responses.activate
    def test_wait_timeout_tells_stuck_resources(self):
        # The HA manager picked a target that refuses the migration: the resource stays in migrate state
        status = _with("pve-devel-1", "maintenance", "maintenance", node_request=["pve-devel-1"])
        status["manager_status"]["service_status"]["vm:100"].update(state="migrate", target="pve-devel-2")
        with patch("pvecontrol.actions.ha.time.monotonic", side_effect=itertools.count(step=10)):
            result = self._run(["ha", "status", "pve-devel-1", "--wait", "--timeout", "15"], [status])
        assert result.exit_code == 1
        assert "vm:100 (migrate from pve-devel-1 to pve-devel-2)" in self.errors[0]
        assert "Waiting for node pve-devel-1, HA state maintenance" in self.logs[-2]

    @responses.activate
    def test_wait_log_names_the_first_resources(self):
        # A node with many HA resources: the log of each round names the first ones and counts the others, the
        # timeout error names them all
        services = {f"vm:{vmid}": "pve-devel-1" for vmid in range(200, 208)}
        status = _with("pve-devel-1", "maintenance", "maintenance", services=services, node_request=["pve-devel-1"])
        with patch("pvecontrol.actions.ha.time.monotonic", side_effect=itertools.count(step=10)):
            result = self._run(["ha", "status", "pve-devel-1", "--wait", "--timeout", "15"], [status])
        assert result.exit_code == 1
        assert self.logs[-2].endswith("vm:204 (started), and 3 more")
        assert "vm:207 (started)" in self.errors[0]


class HaMaintenanceTestcase(HaCommandsTestcase):

    @responses.activate
    def test_enable(self):
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [_status()])
        assert result.exit_code == 0, result.output
        assert self._writes("PUT") == [(f"{API}/nodes/pve-devel-1/maintenance", {"maintenance-mode": ["enable"]})]
        assert "Maintenance mode enable requested for node pve-devel-1" in result.stdout
        assert self.warnings == [
            "1 VM(s) not managed by HA stay on node pve-devel-1, use node evacuate to move them. "
            "List them with: pvecontrol vm list --filter node '^pve-devel-1$' --filter ha_state '^-$'"
        ]

    @responses.activate
    def test_enable_declined(self):
        result = self._run(["ha", "maintenance-enable", "pve-devel-1"], [_status()], answer="n\n")
        assert result.exit_code == 1
        assert not self._writes("PUT")

    @responses.activate
    def test_enable_unknown_node(self):
        result = self._run(["ha", "maintenance-enable", "pve-unknown", "--force"], [_status()])
        assert result.exit_code == 1
        assert self.errors == ["Node pve-unknown does not exist"]

    @responses.activate
    def test_enable_offline_node(self):
        self.cluster.find_node("pve-devel-1").status = NodeStatus.OFFLINE
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [_status()])
        assert result.exit_code == 1
        assert "pve-devel-1 is not online" in self.errors[0]
        assert not self._writes("PUT")

    @responses.activate
    def test_enable_old_version(self):
        result = self._run(["ha", "maintenance-enable", "pve-devel-3", "--force"], [_status()])
        assert result.exit_code == 1
        assert "node pve-devel-3 runs 9.1.4" in self.errors[0]
        assert "ha-manager crm-command node-maintenance enable pve-devel-3" in self.errors[0]
        assert not self._writes("PUT")

    @responses.activate
    def test_enable_old_api_node(self):
        # The node serving the API answers 501 to a method it doesn't know, it doesn't proxy it to the node
        self.cluster.version = {"version": "9.2.4", "release": "9.2"}
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [_status()])
        assert result.exit_code == 1
        assert "the node serving the API runs 9.2.4" in self.errors[0]
        assert "ha-manager crm-command node-maintenance enable pve-devel-1" in self.errors[0]
        assert not self._writes("PUT")

    @responses.activate
    def test_enable_not_implemented(self):
        # Behind a load balancer, another node than the one that served the version may answer
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [_status()], put_status=501)
        assert result.exit_code == 1
        assert "doesn't know the maintenance API" in self.errors[0]
        assert "Sys.Modify" not in self.errors[0]

    @responses.activate
    def test_enable_forbidden(self):
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [_status()], put_status=403)
        assert result.exit_code == 1
        assert "requires Sys.Modify on /" in self.errors[0]

    @responses.activate
    def test_enable_refused(self):
        # Proxmox VE returns the first line of the error of ha-manager only, it may be an unrelated warning
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [_status()], put_status=500)
        assert result.exit_code == 1
        assert "Sys.Modify" not in self.errors[0]
        assert "see it all: ha-manager crm-command node-maintenance enable pve-devel-1" in self.errors[0]

    @responses.activate
    def test_enable_while_disarmed(self):
        status = _status(disarm={"mode": "freeze", "state": "disarmed"})
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [status])
        assert result.exit_code == 1
        assert "HA is disarmed, no node can enter the maintenance mode" in self.errors[0]
        assert not self._writes("PUT")

    @responses.activate
    def test_enable_untracked_node(self):
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [[]])
        assert result.exit_code == 1
        assert "pve-devel-1 is not tracked by the HA manager" in self.errors[0]
        assert not self._writes("PUT")

    @responses.activate
    def test_enable_fenced_node(self):
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force"], [_with("pve-devel-1", "fence")])
        assert result.exit_code == 1
        assert "pve-devel-1 is in HA state fence" in self.errors[0]
        assert not self._writes("PUT")

    @responses.activate
    def test_disable_while_disarmed(self):
        # Only entering the maintenance mode is refused while HA is disarmed
        status = _with("pve-devel-1", "maintenance", "maintenance", disarm={"mode": "freeze", "state": "disarmed"})
        result = self._run(["ha", "maintenance-disable", "pve-devel-1", "--force"], [status])
        assert result.exit_code == 0, result.output
        assert len(self._writes("PUT")) == 1

    @responses.activate
    def test_enable_wait(self):
        statuses = [
            _status(),
            _with("pve-devel-1", "online", node_request=["pve-devel-1"]),
            _with("pve-devel-1", "maintenance", "maintenance", node_request=["pve-devel-1"]),
            _with("pve-devel-1", "maintenance", "maintenance", services=DRAINED, node_request=["pve-devel-1"]),
        ]
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force", "--wait"], statuses)
        assert result.exit_code == 0, result.output
        assert "Node pve-devel-1 is in HA state maintenance" in self.logs
        assert any("1 VM(s) not managed by HA stay on node pve-devel-1" in msg for msg in self.warnings)

    @responses.activate
    def test_enable_wait_disarmed_meanwhile(self):
        # Disarmed in freeze mode during the drain: the frozen resource doesn't count as active, the node would look
        # drained while it still runs on it
        frozen = _with(
            "pve-devel-1",
            "maintenance",
            "maintenance",
            node_request=["pve-devel-1"],
            disarm={"mode": "freeze", "state": "disarmed"},
        )
        frozen["manager_status"]["service_status"]["vm:100"]["state"] = "freeze"
        result = self._run(["ha", "maintenance-enable", "pve-devel-1", "--force", "--wait"], [_status(), frozen])
        assert result.exit_code == 1
        assert "HA is disarmed while node pve-devel-1 enters the maintenance mode" in self.errors[0]

    @responses.activate
    def test_disable_wait(self):
        statuses = [
            _with("pve-devel-2", "maintenance", "maintenance", services={}),
            _with("pve-devel-2", "maintenance", "active", services={}),
            _with("pve-devel-2", "online"),
        ]
        result = self._run(["ha", "maintenance-disable", "pve-devel-2", "--force", "--wait"], statuses)
        assert result.exit_code == 0, result.output
        assert self._writes("PUT") == [(f"{API}/nodes/pve-devel-2/maintenance", {"maintenance-mode": ["disable"]})]
        assert "Node pve-devel-2 is in HA state online" in self.logs


class HaArmTestcase(HaCommandsTestcase):

    @responses.activate
    def test_disarm_wait(self):
        statuses = [
            _status(disarm={"mode": "freeze", "state": "disarming"}),
            _status(disarm={"mode": "freeze", "state": "disarmed"}),
        ]
        result = self._run(["ha", "disarm", "--mode", "freeze", "--force", "--wait"], statuses)
        assert result.exit_code == 0, result.output
        assert self._writes("POST") == [(f"{API}/cluster/ha/status/disarm-ha", {"resource-mode": ["freeze"]})]
        assert "HA is disarmed" in result.stdout

    @responses.activate
    def test_disarm_requires_mode(self):
        result = self._run(["ha", "disarm", "--force"], [_status()])
        assert result.exit_code == 2
        assert not self._writes("POST")

    @responses.activate
    def test_disarm_unsupported(self):
        result = self._run(["ha", "disarm", "--mode", "ignore", "--force"], [_status()], ha_index=HA_INDEX[:2])
        assert result.exit_code == 1
        assert "requires pve-ha-manager 5.1.3" in self.errors[0]
        assert not self._writes("POST")

    @responses.activate
    def test_disarm_refused(self):
        result = self._run(["ha", "disarm", "--mode", "ignore", "--force"], [_status()], post_status=403)
        assert result.exit_code == 1
        assert "requires Sys.Console on /" in self.errors[0]

    @responses.activate
    def test_arm_wait(self):
        statuses = [_status(disarm={"mode": "freeze", "state": "disarmed"}), _status()]
        result = self._run(["ha", "arm", "--wait"], statuses, answer="y\n")
        assert result.exit_code == 0, result.output
        assert self._writes("POST") == [(f"{API}/cluster/ha/status/arm-ha", {})]
        assert "HA is armed" in result.stdout
