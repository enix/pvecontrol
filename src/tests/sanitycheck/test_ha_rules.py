from unittest.mock import PropertyMock, patch

from proxmoxer.core import ResourceException

from pvecontrol.models.cluster import PVECluster
from pvecontrol.sanitycheck.tests.ha_rules import HaRules
from pvecontrol.sanitycheck.checks import CheckCode
from tests.sanitycheck.utils import assert_message
from tests.testcase import PVEControlTestcase
from tests.fixtures.api import fake_ha_resource_affinity_rule, fake_ha_rule


class HaRulesTestcase(PVEControlTestcase):
    """Runs the ha_rules check against the rules given by the subclass"""

    rules = None

    def _build_fixtures(self):
        super()._build_fixtures()
        self.ha_rules = self.rules

    def _post_setup(self):
        self.check = HaRules(self.cluster)
        self.check.run()


class HaRulesOkTestcase(HaRulesTestcase):

    rules = [fake_ha_rule("prefer-1", ["pve-devel-1"], [100]), fake_ha_resource_affinity_rule("apart", [100, 102])]

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.OK, "HA rules checked")


class HaRulesProblemsTestcase(HaRulesTestcase):

    rules = [
        {**fake_ha_rule("off", ["pve-devel-1"], [100]), "disable": 1},
        {
            **fake_ha_resource_affinity_rule("apart", [100, 102]),
            "errors": {"resources": ["rule defines more resources than available nodes"]},
        },
    ]

    def test_check(self):
        messages = self.check.messages
        assert len(messages) == 2
        assert_message(messages[0], CheckCode.CRIT, "'apart'", "rule defines more resources than available nodes")
        assert_message(messages[1], CheckCode.WARN, "'off'", "disabled")


class HaRulesPve8Testcase(HaRulesTestcase):

    def _post_setup(self):
        self.cluster.version = {"version": "8.4.1", "release": "8.4"}
        super()._post_setup()

    def test_check(self):
        assert_message(self.check.messages[0], CheckCode.OK, "before Proxmox VE 9.0")


class HaRulesUnreadableTestcase(HaRulesTestcase):

    def _post_setup(self):
        error = ResourceException(403, "Forbidden", "Permission check failed (/, Sys.Audit)")
        with patch.object(PVECluster, "ha_rules", new_callable=PropertyMock, side_effect=error):
            super()._post_setup()

    def test_check(self):
        assert_message(self.check.messages[0], CheckCode.WARN, "can't be read", "Sys.Audit")
