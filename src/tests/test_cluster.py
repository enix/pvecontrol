import responses

from tests.testcase import PVEControlTestcase


class PVEClusterTestcase(PVEControlTestcase):

    def test_find_node(self):
        assert len(self.cluster.nodes) == len(self.nodes)
        assert len(self.cluster.vms) == len(self.vms)
        assert len(self.cluster.nodes[0].vms) == 2
        assert len(self.cluster.nodes[1].vms) == 3

        for n in self.nodes:
            node_object = self.cluster.find_node(n["status"]["name"])
            assert node_object.node == n["status"]["name"]

    def test_find_nodes(self):
        node_objects = self.cluster.find_nodes("*devel-1")
        assert len(node_objects) == 1
        assert node_objects[0].node == "pve-devel-1"

        node_objects = self.cluster.find_nodes("pve-devel-*")
        assert len(node_objects) == len(self.nodes)

        node_objects = self.cluster.find_nodes("*pve-devel-[13]")
        assert len(node_objects) == 2
        assert node_objects[0].node == "pve-devel-1"
        assert node_objects[1].node == "pve-devel-3"

        node_objects = self.cluster.find_nodes("*prod*")
        assert len(node_objects) == 0


class PVEClusterHaApiTestcase(PVEControlTestcase):
    """The ha property picks cluster/ha/rules from PVE 9.1 on, cluster/ha/groups before."""

    def _ha_api_used(self, release):
        self.cluster.version = {"release": release, "version": f"{release}.0", "repoid": "deadbeef"}
        self.cluster._ha = None  # pylint: disable=protected-access
        with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
            for path in ("rules", "groups", "status/manager_status", "resources"):
                mock.get(f"https://host:8006/api2/json/cluster/ha/{path}", json={"data": []})
            _ = self.cluster.ha
            called = {call.request.url.split("?")[0] for call in mock.calls}
        rules = "https://host:8006/api2/json/cluster/ha/rules" in called
        groups = "https://host:8006/api2/json/cluster/ha/groups" in called
        assert rules != groups
        return "rules" if rules else "groups"

    def test_ha_api_by_release(self):
        expected = {
            "8.4": "groups",
            "9.0": "groups",
            "9.1": "rules",
            "9.2": "rules",
            "9.10": "rules",
            "10.0": "rules",
        }
        for release, api in expected.items():
            with self.subTest(release=release):
                assert self._ha_api_used(release) == api
