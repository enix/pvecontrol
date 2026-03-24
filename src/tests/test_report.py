import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import responses

from tests.fixtures.api import (
    create_response_wrapper,
    fake_node,
    fake_vm,
    fake_backup,
    fake_backup_job,
    fake_storage_resource,
    fake_ha_rule,
    fake_ha_resource,
    fake_user,
)
from pvecontrol.actions.report import _build_report_data, _build_ha_vmid_group_mapping, _render_report
from pvecontrol.models.cluster import PVECluster


def _make_cluster(
    nodes, vms, backup_jobs=None, storage_resources=None, storages_contents=None, ha_rules=None, ha_resources=None, users=None
):
    """Helper to create a PVECluster with all routes registered in the current responses context."""
    backup_jobs = backup_jobs or []
    storage_resources = storage_resources or []
    storages_contents = storages_contents or {node["status"]["name"]: {} for node in nodes}

    wrapper = create_response_wrapper(
        nodes,
        vms,
        backup_jobs,
        storage_resources,
        storages_contents,
        ha_rules=ha_rules,
        ha_resources=ha_resources,
        users=users,
    )
    wrapper("/api2/json/version")
    wrapper("/api2/json/cluster/status")
    wrapper("/api2/json/cluster/resources")
    for node in nodes:
        name = node["status"]["name"]
        wrapper(f"/api2/json/nodes/{name}/version")
        wrapper(f"/api2/json/nodes/{name}/qemu")
    for vm in vms:
        wrapper(f"/api2/json/nodes/{vm['node']}/qemu/{vm['vmid']}/config")
    for node in nodes:
        name = node["status"]["name"]
        for storage in storage_resources or []:
            wrapper(f"/api2/json/nodes/{name}/storage/{storage['storage']}/content", params={"content": "backup"})
    wrapper("/api2/json/cluster/ha/rules")
    wrapper("/api2/json/cluster/ha/status/manager_status")
    wrapper("/api2/json/cluster/ha/resources")
    wrapper("/api2/json/cluster/backup")
    wrapper("/api2/json/access/users")

    with patch("proxmoxer.backends.https.ProxmoxHTTPAuth") as mock_auth:
        mock_auth_instance = mock_auth.return_value
        mock_auth_instance.timeout = 1
        cluster = PVECluster(
            "name",
            "host",
            config={"node": {"cpufactor": 2.5, "memoryminimum": 0}, "vm": {"max_last_backup": 100}},
            verify_ssl=False,
            **{"user": "user", "password": "password"},
            timeout=mock_auth_instance.timeout,
        )
    return cluster


class ReportTestcase(unittest.TestCase):
    """Tests for report generation with no HA groups configured."""

    @responses.activate
    def setUp(self):
        nodes = [fake_node(1, True), fake_node(2, True), fake_node(3, True)]
        self.nodes = nodes
        self.vms = [
            fake_vm(100, nodes[0]),
            fake_vm(101, nodes[0]),
            fake_vm(102, nodes[1]),
            fake_vm(103, nodes[1]),
            fake_vm(104, nodes[2]),
        ]
        backup_jobs = [fake_backup_job(1, "100"), fake_backup_job(2, "101")]
        storage_resources = [fake_storage_resource("s3", n["status"]["name"]) for n in nodes]
        backups = [fake_backup("s3", 100, datetime.now() - timedelta(minutes=110))]
        storages_contents = {node["status"]["name"]: {"s3": backups} for node in nodes}
        self.users = [
            fake_user("admin@pam", groups=["admins"], expire=0,
                      firstname="Alice", lastname="Admin", email="alice@example.com", realm_type="pam"),
            fake_user("bob@pve", groups=["ops"], expire=1900000000,
                      firstname="Bob", lastname="Builder", email="bob@example.com", realm_type="pve"),
            fake_user("carol@pve", enable=0),
        ]

        cluster = _make_cluster(nodes, self.vms, backup_jobs, storage_resources, storages_contents, users=self.users)
        # preload ha (lazy) while responses mock is still active
        _ = cluster.ha
        self.data = _build_report_data(cluster)

    def test_build_report_data_structure(self):
        assert "generated_at" in self.data
        assert "cluster" in self.data
        assert "version" in self.data
        assert "status" in self.data
        assert "resource_overview" in self.data
        assert "vm_summary" in self.data
        assert "nodes" in self.data
        assert "ha_groups" in self.data
        assert "vm_list" in self.data
        assert "storages" in self.data
        assert "backup_jobs" in self.data
        assert "users" in self.data
        assert "sanity_checks" in self.data

    def test_build_report_cluster_info(self):
        assert self.data["cluster"] == "name"
        assert self.data["status"] == "healthy"

    def test_build_report_resource_overview(self):
        overview = self.data["resource_overview"]
        assert len(overview) == 3
        resources = [row["resource"] for row in overview]
        assert "CPU" in resources
        assert "Memory" in resources
        assert "Disk" in resources

    def test_build_report_nodes(self):
        nodes = self.data["nodes"]
        assert len(nodes) == len(self.nodes)
        for node in nodes:
            assert "node" in node
            assert "status" in node
            assert "vms" in node
            assert "used cpu" in node
            assert "allocated cpu" in node
            assert "total cpu" in node
            assert "used memory" in node
            assert "allocated memory" in node
            assert "total memory" in node

    def test_build_report_vm_summary(self):
        summary = self.data["vm_summary"]
        assert len(summary) == 1
        row = summary[0]
        assert row["total"] == len(self.vms)
        assert row["running"] + row["stopped"] == row["total"]
        assert "templates" in row

    def test_build_report_vm_list(self):
        vm_list = self.data["vm_list"]
        for vm in vm_list:
            assert "vmid" in vm
            assert "name" in vm
            assert "status" in vm
            assert "node" in vm
            assert "cpus" in vm
            assert "template" in vm
            assert "ha group" in vm
            assert "backup jobs" in vm
        vmids = [vm["vmid"] for vm in vm_list]
        assert vmids == sorted(vmids)

    def test_build_report_backup_jobs(self):
        backup_jobs = self.data["backup_jobs"]
        assert len(backup_jobs) == 2
        for job in backup_jobs:
            assert "id" in job
            assert "target storage" in job
            assert "schedule" in job
            assert "nodes" in job
            assert "enabled" in job
            assert "vm selection" in job

    def test_backup_job_vm_selection_text(self):
        by_id = {job["id"]: job for job in self.data["backup_jobs"]}
        # fake_backup_job(1, "100") targets vmid "100" explicitly
        assert by_id["backup-d71917f0-0001"]["vm selection"] == "100"
        assert by_id["backup-d71917f0-0002"]["vm selection"] == "101"

    def test_backup_job_enabled_display(self):
        for job in self.data["backup_jobs"]:
            assert job["enabled"] in ("Yes", "No")

    def test_backup_job_node_all_when_no_node(self):
        for job in self.data["backup_jobs"]:
            assert job["nodes"] == "All"

    def test_vm_list_backup_jobs_association(self):
        by_vmid = {vm["vmid"]: vm for vm in self.data["vm_list"]}
        assert by_vmid[100]["backup jobs"] != ""
        assert by_vmid[101]["backup jobs"] != ""
        assert by_vmid[102]["backup jobs"] == ""

    def test_build_report_storages(self):
        storages = self.data["storages"]
        assert len(storages) > 0
        for storage in storages:
            assert "storage" in storage
            assert "nodes" in storage
            assert "shared" in storage

    def test_storage_nodes_all_when_on_all_nodes(self):
        # storage "s3" is created on all 3 nodes in setUp
        storages = self.data["storages"]
        s3 = next(s for s in storages if s["storage"] == "s3")
        assert s3["nodes"] == "All"

    def test_build_report_users_present(self):
        assert "users" in self.data

    def test_build_report_users_fields(self):
        for user in self.data["users"]:
            assert "userid" in user
            assert "firstname" in user
            assert "lastname" in user
            assert "email" in user
            assert "realm-type" in user
            assert "enabled" in user
            assert "expire" in user
            assert "groups" in user

    def test_build_report_users_sorted(self):
        userids = [u["userid"] for u in self.data["users"]]
        assert userids == sorted(userids)

    def test_build_report_users_expire_never(self):
        by_id = {u["userid"]: u for u in self.data["users"]}
        assert by_id["admin@pam"]["expire"] == "Never"

    def test_build_report_users_expire_date(self):
        by_id = {u["userid"]: u for u in self.data["users"]}
        assert by_id["bob@pve"]["expire"] != "Never"

    def test_build_report_users_enabled(self):
        by_id = {u["userid"]: u for u in self.data["users"]}
        assert by_id["admin@pam"]["enabled"] == "Yes"
        assert by_id["carol@pve"]["enabled"] == "No"

    def test_build_report_users_groups(self):
        by_id = {u["userid"]: u for u in self.data["users"]}
        assert "admins" in by_id["admin@pam"]["groups"]

    def test_render_report_sections(self):
        md = _render_report(self.data)
        assert f"# Cluster Report: {self.data['cluster']}" in md
        assert "**Generated**" in md
        assert "**Version**" in md
        assert "**Status**" in md
        assert "## Resources Overview" in md
        assert "## Proxmox VE Nodes" in md
        assert "## High Availability Groups" in md
        assert "## Sanity Checks" in md
        assert "## Backup Jobs" in md
        assert "## Virtual Machines" in md
        assert "## Storage" in md
        assert "## Users" in md

    def test_render_report_contains_data(self):
        md = _render_report(self.data)
        assert self.data["generated_at"] in md
        assert self.data["status"] in md
        for node in self.data["nodes"]:
            assert node["node"] in md

    def test_ha_groups_empty_when_none_configured(self):
        assert self.data["ha_groups"] == []

    def test_render_report_no_ha_groups_message(self):
        md = _render_report(self.data)
        assert "No HA groups configured." in md

    def test_vm_list_ha_group_empty_when_no_ha(self):
        for vm in self.data["vm_list"]:
            assert vm["ha group"] == ""


class ReportWithHaRulesTestcase(unittest.TestCase):
    """Tests for HA data using new Proxmox >= 9.1 rules API."""

    @responses.activate
    def setUp(self):
        nodes = [fake_node(1, True), fake_node(2, True)]
        self.nodes = nodes
        self.vms = [
            fake_vm(100, nodes[0]),
            fake_vm(101, nodes[0]),
            fake_vm(102, nodes[1]),
        ]
        self.ha_rules = [
            fake_ha_rule("group-az1", ["pve-devel-1", "pve-devel-2"], [100, 101]),
            fake_ha_rule("group-az2", ["pve-devel-2"], [102]),
        ]

        cluster = _make_cluster(nodes, self.vms, ha_rules=self.ha_rules)
        _ = cluster.ha
        self.cluster = cluster
        self.data = _build_report_data(cluster)

    def test_ha_groups_count(self):
        assert len(self.data["ha_groups"]) == 2

    def test_ha_groups_fields(self):
        for group in self.data["ha_groups"]:
            assert "group" in group
            assert "nodes" in group
            assert "node count" in group
            assert "vms" in group

    def test_ha_groups_vm_count(self):
        by_name = {g["group"]: g for g in self.data["ha_groups"]}
        assert by_name["group-az1"]["vms"] == 2
        assert by_name["group-az2"]["vms"] == 1

    def test_ha_groups_node_count(self):
        by_name = {g["group"]: g for g in self.data["ha_groups"]}
        assert by_name["group-az1"]["node count"] == 2
        assert by_name["group-az2"]["node count"] == 1

    def test_vm_list_ha_group_populated(self):
        by_vmid = {vm["vmid"]: vm for vm in self.data["vm_list"]}
        assert by_vmid[100]["ha group"] == "group-az1"
        assert by_vmid[101]["ha group"] == "group-az1"
        assert by_vmid[102]["ha group"] == "group-az2"

    def test_vmid_group_mapping_new_api(self):
        mapping = _build_ha_vmid_group_mapping(self.cluster)
        assert mapping[100] == "group-az1"
        assert mapping[101] == "group-az1"
        assert mapping[102] == "group-az2"

    def test_render_report_ha_section(self):
        md = _render_report(self.data)
        assert "## High Availability Groups" in md
        assert "group-az1" in md
        assert "group-az2" in md


class ReportWithHaGroupsTestcase(unittest.TestCase):
    """Tests for HA data using old Proxmox < 9.1 groups API (group field on resources)."""

    @responses.activate
    def setUp(self):
        nodes = [fake_node(1, True), fake_node(2, True)]
        self.vms = [fake_vm(100, nodes[0]), fake_vm(101, nodes[1])]
        self.ha_resources = [
            fake_ha_resource(100, group="legacy-group"),
            fake_ha_resource(101, group="legacy-group"),
        ]

        cluster = _make_cluster(nodes, self.vms, ha_resources=self.ha_resources)
        _ = cluster.ha
        self.cluster = cluster

    def test_vmid_group_mapping_old_api(self):
        mapping = _build_ha_vmid_group_mapping(self.cluster)
        assert mapping[100] == "legacy-group"
        assert mapping[101] == "legacy-group"

    def test_vmid_group_mapping_no_group_field_returns_empty(self):
        self.cluster._ha = {  # pylint: disable=protected-access
            "groups": [],
            "manager_status": [],
            "resources": [fake_ha_resource(100)],
        }
        mapping = _build_ha_vmid_group_mapping(self.cluster)
        assert not mapping
