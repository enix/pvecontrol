from pvecontrol.sanitycheck.tests.ha_groups import HaGroups
from pvecontrol.sanitycheck.checks import CheckCode
from tests.sanitycheck.utils import assert_message
from tests.testcase import PVEControlTestcase
from tests.fixtures.api import fake_ha_rule, fake_ha_resource_affinity_rule


class HaGroupsTestcase(PVEControlTestcase):

    def _build_fixtures(self):
        super()._build_fixtures()
        self.ha_rules = [
            fake_ha_rule("group-az1", ["pve-devel-1", "pve-devel-2"], [100, 101]),
            fake_ha_rule("group-az2", ["pve-devel-2"], [102]),
            fake_ha_resource_affinity_rule("keep-apart", [100, 101]),
        ]

    def _post_setup(self):
        _ = self.cluster.ha

    def test_check(self):
        check = HaGroups(self.cluster)
        check.run()

        assert len(check.messages) == 1
        assert_message(check.messages[0], CheckCode.CRIT, "group-az2", "1 node")


class HaGroupsResourceAffinityOnlyTestcase(PVEControlTestcase):

    def _build_fixtures(self):
        super()._build_fixtures()
        self.ha_rules = [fake_ha_resource_affinity_rule("keep-apart", [100, 101])]

    def _post_setup(self):
        _ = self.cluster.ha

    def test_check(self):
        check = HaGroups(self.cluster)
        check.run()

        assert len(check.messages) == 1
        assert_message(check.messages[0], CheckCode.OK)
