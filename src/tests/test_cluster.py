from unittest.mock import patch

import responses

from pvecontrol.cluster import PVECluster
from tests.fixtures.api import fake_node, fake_vm
from tests.fixtures.api import get_status, get_resources, get_node_resources, get_node_qemu_for_vm, get_qemu_config


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

    responses.get("https://host:8006/api2/json/cluster/status", json={"data": get_status(nodes)})
    responses.get("https://host:8006/api2/json/cluster/resources", json={"data": get_resources(nodes, vms)})
    responses.get("https://host:8006/api2/json/nodes", json={"data": get_node_resources(nodes)})
    responses.get(
        "https://host:8006/api2/json/nodes/pve-devel-3/qemu",
        json={
            "data": [
                get_node_qemu_for_vm(vms[0]),
                get_node_qemu_for_vm(vms[1]),
            ]
        },
    )
    responses.get("https://host:8006/api2/json/nodes/pve-devel-3/qemu/100/config", json={"data": get_qemu_config()})
    responses.get("https://host:8006/api2/json/nodes/pve-devel-3/qemu/101/config", json={"data": get_qemu_config()})
    responses.get(
        "https://host:8006/api2/json/nodes/pve-devel-4/qemu",
        json={
            "data": [
                get_node_qemu_for_vm(vms[2]),
            ]
        },
    )
    responses.get("https://host:8006/api2/json/nodes/pve-devel-4/qemu/102/config", json={"data": get_qemu_config()})
    responses.get("https://host:8006/api2/json/cluster/ha/groups", json={"data": []})
    responses.get("https://host:8006/api2/json/cluster/ha/status/manager_status", json={"data": []})
    responses.get("https://host:8006/api2/json/cluster/ha/resources", json={"data": []})
    responses.get("https://host:8006/api2/json/cluster/tasks", json={"data": []})

    cluster = PVECluster("name", "host", "username", "password", None, timeout=1)
    cluster_vms = cluster.vms()

    assert len(cluster.nodes) == len(nodes)
    assert len(cluster_vms) == len(vms)
    assert len(cluster.nodes[0].vms) == 2
    assert len(cluster.nodes[1].vms) == 1

    for n in nodes:
        node_object = cluster.find_node(n["status"]["name"])
        assert node_object.node == n["status"]["name"]
