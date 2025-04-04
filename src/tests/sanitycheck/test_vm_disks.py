from unittest.mock import patch
from pvecontrol.models.cluster import PVECluster
from pvecontrol.sanitycheck.tests.vm import DiskUnused
from pvecontrol.sanitycheck import SanityCheck
from pvecontrol.sanitycheck.checks import CheckCode
from tests.fixtures.api import (
    mock_api_requests,
    fake_node,
    fake_vm,
    fake_storage_resource,
    fake_storage_content,
    DEFAULT_VM_CONFIG,
)


@patch("proxmoxer.backends.https.ProxmoxHTTPAuth")
@patch("proxmoxer.backends.https.ProxmoxHttpSession.request")
def test_sanitycheck_vm_disk_unused(request, _proxmox_http_auth):
    # VM have unused disks
    nodes = [
        fake_node(3, True),
        fake_node(4, True),
    ]
    vms = [
        fake_vm(100, nodes[0], config={**DEFAULT_VM_CONFIG, "unused1": "vm-100-disk-1.qcow2"}),
        fake_vm(101, nodes[0], config={**DEFAULT_VM_CONFIG, "unused1": "local:101/vm-101-disk-1.qcow2"}),
        fake_vm(102, nodes[1]),
        fake_vm(103, nodes[1]),
    ]

    request.side_effect = mock_api_requests(nodes, vms)

    proxmox = PVECluster(
        "name",
        "host",
        config={},
        **{"user": "user", "password": "password"},
        timeout=1,
    )

    disk_unused_check = DiskUnused(proxmox)
    disk_unused_check.run()

    def assert_message(message, expected_code, *message_contains):
        assert message.code == expected_code
        for string in message_contains:
            assert string in message.message

    sc = SanityCheck(proxmox)
    with patch.object(sc, "_checks", new=[disk_unused_check]):
        exitcode = sc.get_exit_code()
        sc.display()

        assert exitcode == 1
        assert len(disk_unused_check.messages) == 2
        assert_message(disk_unused_check.messages[0], CheckCode.CRIT, "Disk 'unused1' is not used on vm 100/vm-100")
        assert_message(disk_unused_check.messages[1], CheckCode.CRIT, "Disk 'unused1' is not used on vm 101/vm-101")


@patch("proxmoxer.backends.https.ProxmoxHTTPAuth")
@patch("proxmoxer.backends.https.ProxmoxHttpSession.request")
def test_sanitycheck_local_storage_vm_deleted(request, _proxmox_http_auth):
    # Local Storage have unused disks, VM doesn't exist anymore
    nodes = [
        fake_node(3, True),
        fake_node(4, True),
    ]
    vms = [fake_vm(100, nodes[0])]

    storage_resources = [
        fake_storage_resource("local", nodes[0]["status"]["name"], shared=0, plugin_type="lvm"),
        fake_storage_resource("local", nodes[1]["status"]["name"], shared=0, plugin_type="lvm"),
    ]

    storage_content = {
        nodes[0]["status"]["name"]: {
            "local": [fake_storage_content("local", "vm-100-disk-1.qcow2", 100, "image", 1738461900, "qcow2", {})],
        },
        nodes[1]["status"]["name"]: {
            "local": [fake_storage_content("local", "vm-101-disk-1.qcow2", 101, "image", 1738461900, "qcow2", {})],
        },
    }

    request.side_effect = mock_api_requests(
        nodes, vms, storage_resources=storage_resources, storage_content=storage_content
    )

    proxmox = PVECluster(
        "name",
        "host",
        config={},
        **{"user": "user", "password": "password"},
        timeout=1,
    )

    disk_unused_check = DiskUnused(proxmox)
    disk_unused_check.run()

    sc = SanityCheck(proxmox)

    def assert_message(message, expected_code, *message_contains):
        assert message.code == expected_code
        for string in message_contains:
            assert string in message.message

    with patch.object(sc, "_checks", new=[disk_unused_check]):
        exitcode = sc.get_exit_code()
        sc.display()

        assert exitcode == 1
        assert len(disk_unused_check.messages) == 3

        assert_message(disk_unused_check.messages[0], CheckCode.OK, "Storage 'pve-devel-3/local' have 1/1 disk used")
        assert_message(disk_unused_check.messages[1], CheckCode.WARN, "Storage 'pve-devel-4/local' have 0/1 disk used")
        assert_message(
            disk_unused_check.messages[2],
            CheckCode.CRIT,
            "Disk 'pve-devel-4/local:101/vm-101-disk-1.qcow2' is not used, vm 101 doesn't exists on node",
        )


@patch("proxmoxer.backends.https.ProxmoxHTTPAuth")
@patch("proxmoxer.backends.https.ProxmoxHttpSession.request")
def test_sanitycheck_shared_storage_vm_deleted(request, _proxmox_http_auth):
    # Local Storage have unused disks, VM doesn't exist anymore
    nodes = [
        fake_node(3, True),
        fake_node(4, True),
    ]
    vms = [fake_vm(100, nodes[0])]

    storage_resources = [
        fake_storage_resource("shared", nodes[0]["status"]["name"], shared=1, plugin_type="lvm"),
        fake_storage_resource("shared", nodes[1]["status"]["name"], shared=1, plugin_type="lvm"),
    ]

    contents = [
        fake_storage_content("shared", "vm-100-disk-1.qcow2", 100, "image", 1738461900, "qcow2", {}),
        fake_storage_content("shared", "vm-101-disk-1.qcow2", 101, "image", 1738461900, "qcow2", {}),
    ]

    storage_content = {
        nodes[0]["status"]["name"]: {
            "shared": contents,
        },
        nodes[1]["status"]["name"]: {
            "shared": contents,
        },
    }

    request.side_effect = mock_api_requests(
        nodes, vms, storage_resources=storage_resources, storage_content=storage_content
    )

    proxmox = PVECluster(
        "name",
        "host",
        config={},
        **{"user": "user", "password": "password"},
        timeout=1,
    )

    disk_unused_check = DiskUnused(proxmox)
    disk_unused_check.run()

    sc = SanityCheck(proxmox)

    def assert_message(message, expected_code, *message_contains):
        assert message.code == expected_code
        for string in message_contains:
            assert string in message.message

    with patch.object(sc, "_checks", new=[disk_unused_check]):
        exitcode = sc.get_exit_code()
        sc.display()

        assert exitcode == 1
        assert len(disk_unused_check.messages) == 2

        assert_message(
            disk_unused_check.messages[0],
            CheckCode.CRIT,
            "Disk 'pve-devel-3/shared:101/vm-101-disk-1.qcow2' is not used, vm 101 doesn't exists",
        )
        assert_message(
            disk_unused_check.messages[1],
            CheckCode.CRIT,
            "Disk 'pve-devel-4/shared:101/vm-101-disk-1.qcow2' is not used, vm 101 doesn't exists",
        )
