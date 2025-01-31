from unittest.mock import patch

import responses

from pvecontrol.cluster import PVECluster
from tests.fixtures.api import fake_node, fake_vm
from tests.fixtures.api import create_response_wrapper


@patch("proxmoxer.backends.https.ProxmoxHTTPAuth")
@responses.activate
def test_pvecluster_find_node(_proxmox_http_auth):
    nodes = [
        fake_node(3, True),
        fake_node(4, True),
    ]
    vms = [
        fake_vm(100, nodes[0]),
        fake_vm(101, nodes[0]),
        fake_vm(102, nodes[1]),
    ]

    responses_get = create_response_wrapper(nodes, vms)

    responses_get("https://host:8006/api2/json/cluster/status")
    responses_get("https://host:8006/api2/json/cluster/resources")
    responses_get("https://host:8006/api2/json/nodes")
    responses_get("https://host:8006/api2/json/nodes/pve-devel-3/qemu")
    responses_get("https://host:8006/api2/json/nodes/pve-devel-3/qemu/100/config")
    responses_get("https://host:8006/api2/json/nodes/pve-devel-3/qemu/101/config")
    responses_get("https://host:8006/api2/json/nodes/pve-devel-4/qemu")
    responses_get("https://host:8006/api2/json/nodes/pve-devel-4/qemu/102/config")
    responses_get("https://host:8006/api2/json/cluster/ha/groups")
    responses_get("https://host:8006/api2/json/cluster/ha/status/manager_status")
    responses_get("https://host:8006/api2/json/cluster/ha/resources")
    responses_get("https://host:8006/api2/json/cluster/tasks")

    cluster = PVECluster("name", "host", "username", "password", None, timeout=1)
    cluster_vms = cluster.vms()

    assert len(cluster.nodes) == len(nodes)
    assert len(cluster_vms) == len(vms)
    assert len(cluster.nodes[0].vms) == 2
    assert len(cluster.nodes[1].vms) == 1

    for n in nodes:
        node_object = cluster.find_node(n["status"]["name"])
        assert node_object.node == n["status"]["name"]
