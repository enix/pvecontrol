import json
import unittest

from unittest.mock import patch

import responses

from click.testing import CliRunner
from proxmoxer.core import ResourceException

from pvecontrol import pvecontrol
from pvecontrol.models.node import NodeHaState, parse_node_ha_states
from tests.fixtures.api import fake_ha_manager_status
from tests.testcase import PVEControlTestcase

MANAGER_STATUS_PATH = "/cluster/ha/status/manager_status"


class ParseNodeHaStatesTestcase(unittest.TestCase):

    def test_states(self):
        status = fake_ha_manager_status(
            node_status={"a": "online", "b": "maintenance", "c": "unknown", "d": "fence", "e": "gone"}
        )
        assert parse_node_ha_states(status) == {
            "a": NodeHaState.ONLINE,
            "b": NodeHaState.MAINTENANCE,
            "c": NodeHaState.UNKNOWN,
            "d": NodeHaState.FENCE,
            "e": NodeHaState.GONE,
        }

    def test_maintenance_requested(self):
        # The request is recorded while the node is still online, and kept once it is in maintenance
        status = fake_ha_manager_status(node_status={"a": "online", "b": "maintenance"}, node_request=["a", "b"])
        assert parse_node_ha_states(status) == {"a": NodeHaState.MAINTENANCE_REQUESTED, "b": NodeHaState.MAINTENANCE}

    def test_unexpected_state(self):
        assert parse_node_ha_states(fake_ha_manager_status(node_status={"a": "new-state"})) == {"a": NodeHaState.NONE}

    def test_no_ha(self):
        assert not parse_node_ha_states({})
        assert not parse_node_ha_states(fake_ha_manager_status())

    def test_str(self):
        assert str(NodeHaState.NONE) == "-"
        assert str(NodeHaState.MAINTENANCE_REQUESTED) == "maintenance_requested"

    def test_available(self):
        assert NodeHaState.NONE.available
        assert NodeHaState.ONLINE.available
        assert not NodeHaState.MAINTENANCE_REQUESTED.available
        assert not NodeHaState.FENCE.available


class NodeHaStateTestcase(PVEControlTestcase):
    """pve-devel-2 is requested for maintenance, pve-devel-3 is in maintenance"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.ha_manager_status = fake_ha_manager_status(
            node_status={"pve-devel-1": "online", "pve-devel-2": "online", "pve-devel-3": "maintenance"},
            node_request=["pve-devel-2", "pve-devel-3"],
            lrm_modes={"pve-devel-3": "maintenance"},
        )

    def _post_setup(self):
        before = len(responses.calls)
        self.states = {node.node: node.ha_state for node in self.cluster.nodes}
        _ = self.cluster.ha_imbalance
        _ = self.cluster.ha
        self.manager_status_calls = [
            call for call in list(responses.calls)[before:] if call.request.url.endswith(MANAGER_STATUS_PATH)
        ]

    def test_states(self):
        assert self.states == {
            "pve-devel-1": NodeHaState.ONLINE,
            "pve-devel-2": NodeHaState.MAINTENANCE_REQUESTED,
            "pve-devel-3": NodeHaState.MAINTENANCE,
        }

    def test_manager_status_fetched_once(self):
        assert len(self.manager_status_calls) == 1

    def test_node_list(self):
        with patch("pvecontrol.cli.PVECluster.create_from_config", return_value=self.cluster):
            result = CliRunner().invoke(pvecontrol, ["-c", "name", "-o", "json", "node", "list"])
        assert result.exit_code == 0, result.output
        rows = {row["node"]: row["ha_state"] for row in json.loads(result.output)}
        assert rows == {"pve-devel-1": "online", "pve-devel-2": "maintenance_requested", "pve-devel-3": "maintenance"}


class NodeHaStateNoHaTestcase(PVEControlTestcase):
    """HA was never used: manager_status returns no object"""

    def _post_setup(self):
        self.states = {node.node: node.ha_state for node in self.cluster.nodes}

    def test_states(self):
        assert set(self.states.values()) == {NodeHaState.NONE}


class NodeHaStateForbiddenTestcase(PVEControlTestcase):
    """Without Sys.Audit on /, manager_status is refused: every node is NONE, with a single warning"""

    def _register_routes(self):
        super()._register_routes()
        responses.replace(
            responses.GET,
            f"https://host:8006/api2/json{MANAGER_STATUS_PATH}",
            status=403,
            body=json.dumps({"data": None}),
        )

    def _post_setup(self):
        with self.assertLogs("root", level="WARNING") as log:
            self.states = {node.node: node.ha_state for node in self.cluster.nodes}
        self.warnings = log.output

    def test_states(self):
        assert set(self.states.values()) == {NodeHaState.NONE}

    def test_single_warning(self):
        assert len(self.warnings) == 1
        assert "requires Sys.Audit on /" in self.warnings[0]

    def test_ha_manager_status_raises(self):
        with responses.RequestsMock() as mock:
            mock.get(f"https://host:8006/api2/json{MANAGER_STATUS_PATH}", status=403, body=json.dumps({"data": None}))
            with self.assertRaises(ResourceException):
                _ = self.cluster.ha_manager_status
