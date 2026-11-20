from unittest.mock import PropertyMock, patch

from proxmoxer.core import ResourceException

from pvecontrol.models.cluster import PVECluster
from pvecontrol.sanitycheck.tests.ha_nodes import HaNodes
from pvecontrol.sanitycheck.checks import CheckCode
from tests.sanitycheck.utils import assert_message
from tests.testcase import PVEControlTestcase
from tests.fixtures.api import fake_ha_manager_status

ALL_ONLINE = {"pve-devel-1": "online", "pve-devel-2": "online", "pve-devel-3": "online"}


class HaNodesTestcase(PVEControlTestcase):
    """Runs the ha_nodes check against the manager status given by the subclass"""

    manager_status = None

    def _build_fixtures(self):
        super()._build_fixtures()
        self.ha_manager_status = self.manager_status

    def _post_setup(self):
        self.check = HaNodes(self.cluster)
        self.check.run()


class HaNodesOkTestcase(HaNodesTestcase):

    manager_status = fake_ha_manager_status(node_status=ALL_ONLINE)

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.OK, "HA nodes checked")


class HaNodesNoHaTestcase(HaNodesTestcase):
    """HA was never used: manager_status returns no object"""

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.OK)


class HaNodesStatesTestcase(HaNodesTestcase):

    manager_status = fake_ha_manager_status(
        node_status={
            "pve-devel-1": "online",
            "pve-devel-2": "online",
            "pve-devel-3": "maintenance",
            "pve-devel-4": "fence",
            "pve-devel-5": "unknown",
            "pve-devel-6": "gone",
        },
        node_request=["pve-devel-2"],
    )

    def test_check(self):
        messages = self.check.messages
        assert len(messages) == 5
        assert_message(messages[0], CheckCode.WARN, "pve-devel-2", "maintenance mode requested")
        assert_message(messages[1], CheckCode.WARN, "pve-devel-3", "HA maintenance mode")
        assert_message(messages[2], CheckCode.CRIT, "pve-devel-4", "HA state fence")
        assert_message(messages[3], CheckCode.CRIT, "pve-devel-5", "HA state unknown")
        assert_message(messages[4], CheckCode.WARN, "pve-devel-6", "gone")


class HaNodesDisarmedTestcase(HaNodesTestcase):

    manager_status = fake_ha_manager_status(node_status=ALL_ONLINE, disarm={"mode": "freeze", "state": "disarmed"})

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.WARN, "HA is disarmed", "freeze mode")


class HaNodesUnreadableTestcase(HaNodesTestcase):

    def _post_setup(self):
        error = ResourceException(403, "Forbidden", "Permission check failed (/, Sys.Audit)")
        with patch.object(PVECluster, "ha_manager_status", new_callable=PropertyMock, side_effect=error):
            super()._post_setup()

    def test_check(self):
        assert len(self.check.messages) == 1
        assert_message(self.check.messages[0], CheckCode.WARN, "can't be read", "Sys.Audit")
