from unittest.mock import PropertyMock, patch

from proxmoxer.core import ResourceException

from pvecontrol.models.cluster import PVECluster
from pvecontrol.sanitycheck import SanityCheck
from pvecontrol.sanitycheck.checks import CheckCode
from pvecontrol.sanitycheck.tests.ha_crs import HaCrs
from tests.sanitycheck.utils import assert_message
from tests.testcase import PVEControlTestcase
from tests.fixtures.api import (
    fake_cluster_options,
    fake_ha_manager_status,
    fake_ha_resource,
    fake_ha_resource_affinity_rule,
)

ALL_VMS = [100, 101, 102, 103, 104]


class HaCrsTestcase(PVEControlTestcase):
    """Runs the crs check on the 5 running VMs of PVEControlTestcase (1 GiB each).
    By default the settings are sane: static mode, auto-rebalance on, every VM managed by HA, low imbalance."""

    crs = "ha=static,ha-auto-rebalance=1"
    imbalance = 0.1
    ha_vmids = ALL_VMS
    no_auto_rebalance_vmids = []
    affinity_rules = []

    def _build_fixtures(self):
        super()._build_fixtures()
        self.cluster_options = fake_cluster_options(self.crs)
        self.ha_manager_status = fake_ha_manager_status(self.imbalance)
        self.ha_resources = [
            fake_ha_resource(vmid, auto_rebalance=False if vmid in self.no_auto_rebalance_vmids else None)
            for vmid in self.ha_vmids
        ]
        self.ha_rules = [
            fake_ha_resource_affinity_rule(f"rule-{i}", vmids, affinity)
            for i, (vmids, affinity) in enumerate(self.affinity_rules)
        ]

    def _post_setup(self):
        self.check = HaCrs(self.cluster)
        self.check.run()
        self.exitcode = SanityCheck(self.cluster, colors=False, unicode=False).run(checks=["crs"])

    def _codes(self):
        return [message.code for message in self.check.messages]


class HaCrsOkTestcase(HaCrsTestcase):

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.OK, "CRS settings checked")
        assert self.exitcode == 0


class HaCrsDefaultsTestcase(HaCrsTestcase):
    """No crs in datacenter.cfg, no HA resource, and no imbalance reported (PVE < 9.2)"""

    crs = None
    imbalance = None
    ha_vmids = []

    def test_check(self):
        assert self._codes() == [CheckCode.OK]


class HaCrsImbalanceUnknownTestcase(HaCrsTestcase):

    imbalance = None

    def test_check(self):
        assert self._codes() == [CheckCode.OK]


class HaCrsBasicAutoRebalanceTestcase(HaCrsTestcase):

    crs = "ha=basic,ha-auto-rebalance=1"

    def test_check(self):
        assert self._codes() == [CheckCode.WARN, CheckCode.CRIT]
        assert_message(self.check.messages[0], CheckCode.WARN, "basic", "static or dynamic")
        assert_message(self.check.messages[1], CheckCode.CRIT, "ignored in CRS mode basic")
        assert self.exitcode == 1


class HaCrsBasicWithResourcesTestcase(HaCrsTestcase):

    crs = "ha=basic"

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.WARN, "basic", "ignoring CPU and memory")
        assert self.exitcode == 0


class HaCrsNoBalancingTestcase(HaCrsTestcase):
    """Threshold and margin both 0: the HA manager skips balancing, the other settings don't matter"""

    crs = "ha=static,ha-auto-rebalance=1,ha-auto-rebalance-threshold=0,ha-auto-rebalance-margin=0"
    imbalance = None
    ha_vmids = []

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.WARN, "never runs", "both 0")


class HaCrsMarginHoldDurationTestcase(HaCrsTestcase):

    crs = "ha=dynamic,ha-auto-rebalance=1,ha-auto-rebalance-margin=0,ha-auto-rebalance-hold-duration=0"

    def test_check(self):
        assert self._codes() == [CheckCode.WARN, CheckCode.WARN]
        assert_message(self.check.messages[0], CheckCode.WARN, "margin is 0", "ping-pong")
        assert_message(self.check.messages[1], CheckCode.WARN, "hold duration is 0")
        assert self.exitcode == 0


class HaCrsNoMovableResourceTestcase(HaCrsTestcase):

    no_auto_rebalance_vmids = ALL_VMS

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.WARN, "no HA resource can be moved")


class HaCrsPositiveAffinityTestcase(HaCrsTestcase):
    """vm 100 can't move, and 101 to 104 are chained to it by positive affinities"""

    no_auto_rebalance_vmids = [100]
    affinity_rules = [([100, 101], "positive"), ([101, 102, 103], "positive"), ([103, 104], "positive")]

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.WARN, "no HA resource can be moved")


class HaCrsNegativeAffinityTestcase(HaCrsTestcase):
    """A negative affinity doesn't tie the resources together: 101 to 104 can still move"""

    no_auto_rebalance_vmids = [100]
    affinity_rules = [([100, 101, 102, 103, 104], "negative")]

    def test_check(self):
        assert self._codes() == [CheckCode.OK]


class HaCrsNoResourceTestcase(HaCrsTestcase):

    ha_vmids = []

    def test_check(self):
        assert self._codes() == [CheckCode.WARN, CheckCode.INFO]
        assert_message(self.check.messages[0], CheckCode.WARN, "no HA resource to move")
        assert_message(self.check.messages[1], CheckCode.INFO, "100%", "not managed by HA")


class HaCrsNonHaLoadTestcase(HaCrsTestcase):
    """3 GiB of the 5 GiB of running VMs are not managed by HA"""

    ha_vmids = [100, 101]

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.INFO, "60%", "not managed by HA")
        assert self.exitcode == 0


class HaCrsNonHaLoadBelowTestcase(HaCrsTestcase):

    ha_vmids = [100, 101, 102]

    def test_check(self):
        assert self._codes() == [CheckCode.OK]


class HaCrsNonHaLoadAutoRebalanceOffTestcase(HaCrsTestcase):
    """The share of the load not managed by HA only matters to the auto-rebalancer"""

    crs = "ha=static"
    ha_vmids = []

    def test_check(self):
        assert self._codes() == [CheckCode.OK]


class HaCrsImbalanceAutoRebalanceOnTestcase(HaCrsTestcase):

    imbalance = 0.425

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.CRIT, "42.5%", "threshold 30%", "is enabled")
        assert self.exitcode == 1


class HaCrsImbalanceAutoRebalanceOffTestcase(HaCrsTestcase):

    crs = "ha=static,ha-auto-rebalance-threshold=12.5"
    imbalance = 0.2

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.CRIT, "20.0%", "threshold 12.5%", "is disabled")
        assert self.exitcode == 1


class HaCrsImbalanceAtThresholdTestcase(HaCrsTestcase):

    imbalance = 0.3

    def test_check(self):
        assert self._codes() == [CheckCode.OK]


class HaCrsUnreadableTestcase(HaCrsTestcase):
    """cluster/options needs Sys.Audit on /"""

    def _post_setup(self):
        error = ResourceException(403, "Forbidden", "Permission check failed (/, Sys.Audit)")
        with patch.object(PVECluster, "crs", new_callable=PropertyMock, side_effect=error):
            super()._post_setup()

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.WARN, "can't be read")
        assert self.exitcode == 0
