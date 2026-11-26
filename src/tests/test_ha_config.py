import json
import re
import unittest

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import responses

from proxmoxer.core import ResourceException

from pvecontrol.models.ha import PVEHaRule, rule_conflicts
from tests.fixtures.api import (
    fake_ha_manager_status,
    fake_ha_resource,
    fake_ha_resource_affinity_rule,
    fake_ha_rule,
)
from tests.testcase import PVEControlTestcase

API = "https://host:8006/api2/json"
NODES = ["pve-devel-1", "pve-devel-2", "pve-devel-3"]


class HaConfigTestcase(PVEControlTestcase):
    """vm:100 (on pve-devel-1, in the node affinity rule prefer-1) and vm:102 (on pve-devel-2) are HA resources"""

    logs = errors = warnings = ()

    def _build_fixtures(self):
        super()._build_fixtures()
        self.resources = [{**fake_ha_resource(100), "max_restart": 3, "comment": "db"}, fake_ha_resource(102)]
        self.rules = [fake_ha_rule("prefer-1", ["pve-devel-1:2", "pve-devel-2"], [100])]
        self.manager_status = fake_ha_manager_status(
            node_status={node: "online" for node in NODES},
            service_status={"vm:100": "pve-devel-1", "vm:102": "pve-devel-2"},
        )

    def _run(self, args, answer=None, write_status=200, rules_status=200):
        """Run the command, the writes answering write_status"""
        responses.reset()
        responses.get(f"{API}/cluster/ha/resources", body=json.dumps({"data": self.resources}))
        responses.get(f"{API}/cluster/ha/rules", status=rules_status, body=json.dumps({"data": self.rules}))
        responses.get(f"{API}/cluster/ha/status/manager_status", body=json.dumps({"data": self.manager_status}))
        url = re.compile(rf"{API}/cluster/ha/(resources|rules)(/.*)?")
        for method in (responses.POST, responses.PUT, responses.DELETE):
            responses.add(method, url, status=write_status, body=json.dumps({"data": None}))
        # pylint: disable=protected-access
        self.cluster._ha_manager_status = None
        self.cluster._ha_rules = None
        with (
            patch("pvecontrol.actions.ha_config.PVECluster.create_from_config", return_value=self.cluster),
            patch("pvecontrol.cli.PVECluster.create_from_config", return_value=self.cluster),
        ):
            return self._invoke_logged(args, answer)

    @staticmethod
    def _writes():
        """The writes sent, as (method, path, params) with the params of the body or of the query string"""
        writes = []
        for call in responses.calls:
            if call.request.method == "GET":
                continue
            url = urlparse(call.request.url)
            params = parse_qs(call.request.body or "") or parse_qs(url.query)
            writes.append((call.request.method, url.path.removeprefix("/api2/json/"), params))
        return writes


class HaResourceTestcase(HaConfigTestcase):

    @responses.activate
    def test_list(self):
        result = self._run(["-o", "json", "ha", "resource-list"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == [
            {
                "vmid": 100,
                "name": "vm-100",
                "node": "pve-devel-1",
                "state": "started",
                "ha_state": "started",
                "max_restart": 3,
                "max_relocate": 1,
                "failback": True,
                "auto_rebalance": True,
                "rules": "prefer-1",
                "comment": "db",
            },
            {
                "vmid": 102,
                "name": "vm-102",
                "node": "pve-devel-2",
                "state": "started",
                "ha_state": "started",
                "max_restart": 1,
                "max_relocate": 1,
                "failback": True,
                "auto_rebalance": True,
                "rules": "",
                "comment": "",
            },
        ]

    @responses.activate
    def test_list_empty(self):
        self.resources = []
        result = self._run(["-o", "json", "ha", "resource-list"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == []

    @responses.activate
    def test_add(self):
        args = ["ha", "resource-add", "101", "103", "--state", "stopped", "--max-restart", "2", "--no-failback"]
        result = self._run([*args, "--comment", "web", "--force"])
        assert result.exit_code == 0, result.output
        params = {"state": ["stopped"], "max_restart": ["2"], "failback": ["0"], "comment": ["web"]}
        assert self._writes() == [
            ("POST", "cluster/ha/resources", {"sid": ["vm:101"], **params}),
            ("POST", "cluster/ha/resources", {"sid": ["vm:103"], **params}),
        ]

    @responses.activate
    def test_add_api_defaults(self):
        result = self._run(["ha", "resource-add", "101", "--force"])
        assert result.exit_code == 0, result.output
        assert self._writes() == [("POST", "cluster/ha/resources", {"sid": ["vm:101"]})]
        assert "to HA: default settings" in result.stdout

    @responses.activate
    def test_add_declined(self):
        result = self._run(["ha", "resource-add", "101"], answer="n\n")
        assert result.exit_code == 1
        assert not self._writes()

    @responses.activate
    def test_add_checks_every_vm_first(self):
        result = self._run(["ha", "resource-add", "101", "100", "999", "--force"])
        assert result.exit_code == 1
        assert self.errors == [
            "VM 100 is already an HA resource, use ha resource-set to change it",
            "VM 999 does not exist",
        ]
        assert not self._writes()

    @responses.activate
    def test_add_api_error(self):
        result = self._run(["ha", "resource-add", "101", "--force"], write_status=403)
        assert result.exit_code == 1
        assert self.errors[0].startswith("Cannot add HA resource vm:101: 403")

    @responses.activate
    def test_set(self):
        result = self._run(["ha", "resource-set", "100", "--auto-rebalance", "--comment", "", "--force"])
        assert result.exit_code == 0, result.output
        assert self._writes() == [
            ("PUT", "cluster/ha/resources/vm:100", {"auto-rebalance": ["1"], "delete": ["comment"]}),
        ]

    @responses.activate
    def test_set_stop_warns(self):
        result = self._run(["ha", "resource-set", "100", "--state", "stopped", "--force"])
        assert result.exit_code == 0, result.output
        assert self.warnings == ["The HA manager stops the VM(s) in state stopped"]

    @responses.activate
    def test_set_nothing(self):
        result = self._run(["ha", "resource-set", "100", "--force"])
        assert result.exit_code == 2
        assert "Nothing to change" in result.output

    @responses.activate
    def test_set_not_a_resource(self):
        result = self._run(["ha", "resource-set", "101", "--max-restart", "2", "--force"])
        assert result.exit_code == 1
        assert self.errors == ["VM(s) 101 are not HA resources, add them with ha resource-add"]

    @responses.activate
    def test_remove_purges_the_rules(self):
        result = self._run(["ha", "resource-remove", "100", "--force"])
        assert result.exit_code == 0, result.output
        assert "Delete HA rule prefer-1, it has no resource left" in result.stdout
        assert self._writes() == [("DELETE", "cluster/ha/resources/vm:100", {"purge": ["1"]})]

    @responses.activate
    def test_remove_from_a_shared_rule(self):
        self.rules = [fake_ha_resource_affinity_rule("apart", [100, 102])]
        result = self._run(["ha", "resource-remove", "100", "--force"])
        assert result.exit_code == 0, result.output
        assert "Remove vm:100 from HA rule apart" in result.stdout

    @responses.activate
    def test_remove_no_purge(self):
        result = self._run(["ha", "resource-remove", "100", "--no-purge", "--force"])
        assert result.exit_code == 0, result.output
        assert "Delete HA rule" not in result.stdout
        assert self._writes() == [("DELETE", "cluster/ha/resources/vm:100", {"purge": ["0"]})]


class HaRuleTestcase(HaConfigTestcase):

    @responses.activate
    def test_list(self):
        self.rules.append({**fake_ha_resource_affinity_rule("apart", [100, 102]), "disable": 1})
        self.rules.append(
            {
                **fake_ha_resource_affinity_rule("broken", [100, 102], "positive"),
                "errors": {"resources": ["rule shares two or more resources with a negative resource affinity rule"]},
            }
        )
        result = self._run(["-o", "json", "ha", "rule-list"])
        assert result.exit_code == 0, result.output
        rows = {row["rule"]: row for row in json.loads(result.stdout)}
        assert rows["prefer-1"] == {
            "rule": "prefer-1",
            "type": "node-affinity",
            "affinity": "positive",
            "resources": "vm:100",
            "nodes": "pve-devel-1:2,pve-devel-2",
            "strict": False,
            "state": "enabled",
            "errors": "",
            "comment": "HA rule prefer-1",
        }
        assert rows["apart"]["state"] == "disabled"
        assert rows["apart"]["strict"] == "-"
        assert rows["broken"]["errors"] == (
            "resources: rule shares two or more resources with a negative resource affinity rule"
        )

    @responses.activate
    def test_list_forbidden(self):
        result = self._run(["ha", "rule-list"], rules_status=403)
        assert result.exit_code == 1
        assert "requires Sys.Audit on /" in self.errors[0]

    @responses.activate
    def test_add_anti_affinity(self):
        args = ["ha", "rule-add", "apart", "--type", "resource-affinity", "--resources", "100,vm:102"]
        result = self._run([*args, "--affinity", "negative", "--force"])
        assert result.exit_code == 0, result.output
        assert self._writes() == [
            (
                "POST",
                "cluster/ha/rules",
                {
                    "rule": ["apart"],
                    "type": ["resource-affinity"],
                    "resources": ["vm:100,vm:102"],
                    "affinity": ["negative"],
                },
            )
        ]

    @responses.activate
    def test_add_node_affinity(self):
        args = ["ha", "rule-add", "on-3", "--type", "node-affinity", "--resources", "102", "--nodes", "pve-devel-3"]
        result = self._run([*args, "--strict", "--disable", "--force"])
        assert result.exit_code == 0, result.output
        assert self._writes()[0][2] == {
            "rule": ["on-3"],
            "type": ["node-affinity"],
            "resources": ["vm:102"],
            "nodes": ["pve-devel-3"],
            "strict": ["1"],
            "disable": ["1"],
        }

    @responses.activate
    def test_add_conflicts(self):
        cases = [
            (["--type", "resource-affinity", "--resources", "100", "--affinity", "negative"], "at least two resources"),
            (["--type", "node-affinity", "--resources", "100", "--nodes", "pve-devel-3"], "already in node affinity"),
            (
                ["--type", "node-affinity", "--resources", "102", "--nodes", "pve-devel-3:1", "--affinity", "negative"],
                "can't give node priorities",
            ),
            (
                ["--type", "node-affinity", "--resources", "101", "--nodes", "pve-devel-3"],
                "vm:101 are not HA resources",
            ),
            (["--type", "node-affinity", "--resources", "102", "--nodes", "pve-nope"], "pve-nope do not exist"),
        ]
        for options, error in cases:
            with self.subTest(error=error):
                result = self._run(["ha", "rule-add", "new", *options, "--force"])
                assert result.exit_code == 1
                assert error in self.errors[0]
                assert not self._writes()

    @responses.activate
    def test_add_usage_errors(self):
        cases = [
            (["--type", "node-affinity", "--nodes", "pve-devel-1"], "--resources is required"),
            (["--type", "node-affinity", "--resources", "102"], "--nodes is required"),
            (["--type", "resource-affinity", "--resources", "100,102"], "--affinity is required"),
            (
                ["--type", "resource-affinity", "--resources", "100,102", "--affinity", "positive", "--strict"],
                "only apply to node-affinity",
            ),
            (["--type", "node-affinity", "--resources", "abc", "--nodes", "pve-devel-1"], "abc is not a VMID"),
        ]
        for options, error in cases:
            with self.subTest(error=error):
                result = self._run(["ha", "rule-add", "new", *options, "--force"])
                assert result.exit_code == 2
                assert error in result.output

    @responses.activate
    def test_add_existing(self):
        result = self._run(
            ["ha", "rule-add", "prefer-1", "--type", "node-affinity", "--resources", "102", "--nodes", "pve-devel-1"]
        )
        assert result.exit_code == 1
        assert "already exists" in self.errors[0]

    @responses.activate
    def test_add_refused_by_the_api(self):
        # Proxmox VE loses the reason of the refusal on the way
        args = ["ha", "rule-add", "together", "--type", "resource-affinity", "--resources", "100,102"]
        error = ResourceException(
            500, "Internal Server Error", "create ha rule failed: 400 Rule 'together' is invalid."
        )
        with patch("proxmoxer.core.ProxmoxResource.post", side_effect=error):
            result = self._run([*args, "--affinity", "positive", "--force"])
        assert result.exit_code == 1
        assert "is invalid" in self.errors[0]
        assert "feasibility checks" in self.errors[0]

    @responses.activate
    def test_set(self):
        result = self._run(["ha", "rule-set", "prefer-1", "--disable", "--strict", "--force"])
        assert result.exit_code == 0, result.output
        assert self._writes() == [
            (
                "PUT",
                "cluster/ha/rules/prefer-1",
                {"type": ["node-affinity"], "digest": ["aabbccdd"], "strict": ["1"], "disable": ["1"]},
            )
        ]

    @responses.activate
    def test_set_enable(self):
        self.rules[0]["disable"] = 1
        result = self._run(["ha", "rule-set", "prefer-1", "--enable", "--comment", "", "--force"])
        assert result.exit_code == 0, result.output
        assert self._writes()[0][2]["delete"] == ["comment,disable"]

    @responses.activate
    def test_set_checks_the_updated_rule(self):
        self.rules.append(fake_ha_rule("prefer-2", ["pve-devel-2"], [102]))
        result = self._run(["ha", "rule-set", "prefer-2", "--resources", "100,102", "--force"])
        assert result.exit_code == 1
        assert self.errors == ["HA rule prefer-2 is not valid: vm:100 already in node affinity rule prefer-1"]

    @responses.activate
    def test_set_wrong_type_options(self):
        self.rules.append(fake_ha_resource_affinity_rule("apart", [100, 102]))
        result = self._run(["ha", "rule-set", "apart", "--nodes", "pve-devel-1", "--force"])
        assert result.exit_code == 2

    @responses.activate
    def test_set_unknown(self):
        result = self._run(["ha", "rule-set", "nope", "--disable", "--force"])
        assert result.exit_code == 1
        assert self.errors == ["HA rule nope does not exist"]

    @responses.activate
    def test_remove(self):
        result = self._run(["ha", "rule-remove", "prefer-1", "--force"])
        assert result.exit_code == 0, result.output
        assert self._writes() == [("DELETE", "cluster/ha/rules/prefer-1", {})]


class RuleConflictsTestcase(unittest.TestCase):

    def test_valid(self):
        rule = PVEHaRule(rule="apart", type="resource-affinity", resources="vm:1,vm:2", affinity="negative")
        assert not rule_conflicts(rule, [], NODES)

    def test_disabled_rules_are_not_checked(self):
        rule = PVEHaRule(rule="apart", type="resource-affinity", resources="vm:1", affinity="negative", disable=1)
        assert not rule_conflicts(rule, [], NODES)

    def test_more_resources_than_nodes(self):
        rule = PVEHaRule(rule="apart", type="resource-affinity", resources="vm:1,vm:2,vm:3,vm:4", affinity="negative")
        assert rule_conflicts(rule, [], NODES) == [
            "a negative resource affinity rule can't have more resources than nodes (3)"
        ]

    def test_negative_node_affinity_on_every_node(self):
        rule = PVEHaRule(
            rule="away", type="node-affinity", resources="vm:1", nodes=",".join(NODES), affinity="negative"
        )
        assert rule_conflicts(rule, [], NODES) == ["a negative node affinity rule can't list every node of the cluster"]

    def test_positive_and_negative_share_resources(self):
        rule = PVEHaRule(rule="together", type="resource-affinity", resources="vm:1,vm:2,vm:3", affinity="positive")
        other = PVEHaRule(rule="apart", type="resource-affinity", resources="vm:1,vm:2", affinity="negative")
        disabled = PVEHaRule(
            rule="off", type="resource-affinity", resources="vm:1,vm:3", affinity="negative", disable=1
        )
        assert rule_conflicts(rule, [other, disabled], NODES) == [
            "vm:1, vm:2 are also in negative resource affinity rule apart"
        ]
