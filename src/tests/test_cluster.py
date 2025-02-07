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
