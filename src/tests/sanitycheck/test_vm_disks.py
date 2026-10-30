from unittest.mock import patch

from pvecontrol.sanitycheck.tests.vm import DiskUnused
from pvecontrol.sanitycheck import SanityCheck
from pvecontrol.sanitycheck.checks import CheckCode
from tests.sanitycheck.utils import assert_message
from tests.testcase import PVEEmptyClusterTestcase
from tests.fixtures.api import (
    fake_node,
    fake_vm,
    fake_storage_resource,
    fake_storage_content,
    DEFAULT_VM_CONFIG,
)


class DiskUnusedTestcase(PVEEmptyClusterTestcase):
    """2 nodes, pve-devel-3 and pve-devel-4, subclasses set the VMs and storages"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.nodes = [fake_node(3, True), fake_node(4, True)]

    def _register_routes(self):
        super()._register_routes()
        for node in self.nodes:
            name = node["status"]["name"]
            self.responses_get(f"/api2/json/nodes/{name}/version")
            for storage in self.storage_resources:
                self.responses_get(
                    f"/api2/json/nodes/{name}/storage/{storage['storage']}/content", params={"content": "images"}
                )
        for vm in self.vms:
            self.responses_get(f"/api2/json/nodes/{vm['node']}/qemu/{vm['vmid']}/config")

    def _post_setup(self):
        super()._post_setup()
        self.check = DiskUnused(self.cluster)
        self.check.run()

        sc = SanityCheck(self.cluster)
        with patch.object(sc, "_checks", new=[self.check]):
            self.exitcode = sc.get_exit_code()
            sc.display()


class VmDiskUnusedTestcase(DiskUnusedTestcase):
    """VM have unused disks"""

    def _build_fixtures(self):
        super()._build_fixtures()
        self.vms = [
            fake_vm(100, self.nodes[0], config={**DEFAULT_VM_CONFIG, "unused1": "vm-100-disk-1.qcow2"}),
            fake_vm(101, self.nodes[0], config={**DEFAULT_VM_CONFIG, "unused1": "local:101/vm-101-disk-1.qcow2"}),
            fake_vm(102, self.nodes[1]),
            fake_vm(103, self.nodes[1]),
        ]

    def test_sanitycheck_vm_disk_unused(self):
        assert self.exitcode == 1
        assert len(self.check.messages) == 2
        assert_message(self.check.messages[0], CheckCode.CRIT, "Disk 'unused1' is not used on vm 100/vm-100")
        assert_message(self.check.messages[1], CheckCode.CRIT, "Disk 'unused1' is not used on vm 101/vm-101")


class LocalStorageVmDeletedTestcase(DiskUnusedTestcase):
    """Local Storage have unused disks, VM doesn't exist anymore"""

    def _build_fixtures(self):
        super()._build_fixtures()
        node3, node4 = (node["status"]["name"] for node in self.nodes)
        self.vms = [fake_vm(100, self.nodes[0])]
        self.storage_resources = [
            fake_storage_resource("local", node3, shared=0, plugin_type="lvm"),
            fake_storage_resource("local", node4, shared=0, plugin_type="lvm"),
        ]
        self.storages_contents = {
            node3: {
                "local": [fake_storage_content("local", "vm-100-disk-1.qcow2", 100, "image", 1738461900, "qcow2", {})],
            },
            node4: {
                "local": [fake_storage_content("local", "vm-101-disk-1.qcow2", 101, "image", 1738461900, "qcow2", {})],
            },
        }

    def test_sanitycheck_local_storage_vm_deleted(self):
        assert self.exitcode == 1
        assert len(self.check.messages) == 3

        assert_message(self.check.messages[0], CheckCode.OK, "Storage 'pve-devel-3/local' have 1/1 disk used")
        assert_message(self.check.messages[1], CheckCode.WARN, "Storage 'pve-devel-4/local' have 0/1 disk used")
        assert_message(
            self.check.messages[2],
            CheckCode.CRIT,
            "Disk 'pve-devel-4/local:101/vm-101-disk-1.qcow2' is not used, vm 101 doesn't exists on node",
        )


class SharedStorageVmDeletedTestcase(DiskUnusedTestcase):
    """Shared Storage have unused disks, VM doesn't exist anymore"""

    def _build_fixtures(self):
        super()._build_fixtures()
        node3, node4 = (node["status"]["name"] for node in self.nodes)
        self.vms = [fake_vm(100, self.nodes[0])]
        self.storage_resources = [
            fake_storage_resource("shared", node3, shared=1, plugin_type="lvm"),
            fake_storage_resource("shared", node4, shared=1, plugin_type="lvm"),
        ]
        contents = [
            fake_storage_content("shared", "vm-100-disk-1.qcow2", 100, "image", 1738461900, "qcow2", {}),
            fake_storage_content("shared", "vm-101-disk-1.qcow2", 101, "image", 1738461900, "qcow2", {}),
        ]
        self.storages_contents = {node3: {"shared": contents}, node4: {"shared": contents}}

    def test_sanitycheck_shared_storage_vm_deleted(self):
        assert self.exitcode == 1
        assert len(self.check.messages) == 2

        assert_message(
            self.check.messages[0],
            CheckCode.CRIT,
            "Disk 'pve-devel-3/shared:101/vm-101-disk-1.qcow2' is not used, vm 101 doesn't exists",
        )
        assert_message(
            self.check.messages[1],
            CheckCode.CRIT,
            "Disk 'pve-devel-4/shared:101/vm-101-disk-1.qcow2' is not used, vm 101 doesn't exists",
        )
