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

    cluster = PVECluster(
        "name", "host", config={"node": "node"}, verify_ssl=False, **{"user": "user", "password": "password"}, timeout=1
    )
    cluster_vms = cluster.vms

    assert len(cluster.nodes) == len(nodes)
    assert len(cluster_vms) == len(vms)
    assert len(cluster.nodes[0].vms) == 2
    assert len(cluster.nodes[1].vms) == 1

    for n in nodes:
        node_object = cluster.find_node(n["status"]["name"])
        assert node_object.node == n["status"]["name"]


@patch("proxmoxer.backends.https.ProxmoxHTTPAuth")
@patch("proxmoxer.backends.https.ProxmoxHttpSession.request")
def test_pvecluster_find_nodes(request, _proxmox_http_auth):
    nodes = [
        fake_node(1, True),
        fake_node(2, True),
        fake_node(3, True),
    ]
    vms = []

    request.side_effect = mock_api_requests(nodes, vms)

    cluster = PVECluster(
        "name", "host", config={"node": "node"}, verify_ssl=False, **{"user": "user", "password": "password"}, timeout=1
    )

    node_objects = cluster.find_nodes("*devel-1")
    assert len(node_objects) == 1
    assert node_objects[0].node == "pve-devel-1"

    node_objects = cluster.find_nodes("pve-devel-*")
    assert len(node_objects) == len(nodes)

    node_objects = cluster.find_nodes("*pve-devel-[13]")
    assert len(node_objects) == 2
    assert node_objects[0].node == "pve-devel-1"
    assert node_objects[1].node == "pve-devel-3"

    node_objects = cluster.find_nodes("*prod*")
    assert len(node_objects) == 0


@patch("proxmoxer.backends.https.ProxmoxHTTPAuth")
@patch("proxmoxer.backends.https.ProxmoxHttpSession.request")
def test_pvecluster_http_call_made_on_initstatus(request, _proxmox_http_auth):
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

    _cluster = PVECluster(
        "name", "host", config={"node": "node"}, verify_ssl=False, **{"user": "user", "password": "password"}, timeout=1
    )

    assert request.call_count == 2  # status and ressources
