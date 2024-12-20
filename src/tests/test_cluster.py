from unittest.mock import patch
from pvecontrol.cluster import PVECluster
from tests.fixtures.api import mock_api_requests, fake_node, fake_vm


@patch("proxmoxer.backends.https.ProxmoxHTTPAuth")
@patch("proxmoxer.backends.https.ProxmoxHttpSession.request")
def test_pvecluster_find_node(request, _proxmox_http_auth):
    nodes = [
        fake_node(1, True),
        fake_node(2, True),
    ]
    vms = [
        fake_vm(100, nodes[0]),
        fake_vm(101, nodes[0]),
        fake_vm(102, nodes[1]),
    ]

    request.side_effect = mock_api_requests(nodes, vms)

    cluster = PVECluster("name", "host", "username", "password", None, timeout=1)
    cluster_vms = cluster.vms()

    assert len(cluster.nodes) == len(nodes)
    assert len(cluster_vms) == len(vms)
    assert len(cluster.nodes[0].vms) == 2
    assert len(cluster.nodes[1].vms) == 1

    for n in nodes:
        node_object = cluster.find_node(n["status"]["name"])
        assert node_object.node == n["status"]["name"]
