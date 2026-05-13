from tests.fixtures.api import (
    fake_backup_job,
    fake_ha_rule,
    fake_ha_resource,
    fake_user,
    fake_group,
    fake_acl,
)
from pvecontrol.actions.report import _build_report_data, _build_ha_vmid_group_mapping, _render_report
from tests.testcase import PVEControlTestcase


# FIXME: remove pylint disable annotations
# pylint: disable=too-many-public-methods
class ReportTestcase(PVEControlTestcase):
    """Tests for report generation with no HA groups configured."""

    def _extra_fixtures(self):
        # vm 102 must have no backup job (see test_vm_list_backup_jobs_association)
        self.backup_jobs = [fake_backup_job(1, "100"), fake_backup_job(2, "101")]
        self.users = [
            fake_user(
                "admin@pam",
                groups=["admins"],
                expire=0,
                firstname="Alice",
                lastname="Admin",
                email="alice@example.com",
                realm_type="pam",
                tokens=["ci-token", "backup-token"],
            ),
            fake_user(
                "bob@pve",
                groups=["ops"],
                expire=1900000000,
                firstname="Bob",
                lastname="Builder",
                email="bob@example.com",
                realm_type="pve",
            ),
            fake_user("carol@pve", enable=0),
        ]
        self.groups = [
            fake_group("admins", comment="Administrators", users=["admin@pam"]),
            fake_group("ops", comment="Operations", users=["bob@pve"]),
        ]
        self.acls = [
            fake_acl("/", "admin@pam", "Administrator", acl_type="user", propagate=1),
            fake_acl("/vms", "ops", "PVEVMAdmin", acl_type="group", propagate=0),
        ]

    def _extra_routes(self):
        self._register_full_routes()

    def _cluster_config(self):
        return {"node": {"cpufactor": 2.5, "memoryminimum": 0}, "vm": {"max_last_backup": 100}}

    def _post_setup(self):
        _ = self.cluster.ha
        self.data = _build_report_data(self.cluster)

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
        assert "groups" in self.data
        assert "acls" in self.data
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

    def test_build_report_acls_present(self):
        assert "acls" in self.data

    def test_build_report_acls_count(self):
        assert len(self.data["acls"]) == len(self.acls)

    def test_build_report_acls_fields(self):
        for acl in self.data["acls"]:
            assert "path" in acl
            assert "type" in acl
            assert "ugid" in acl
            assert "roleid" in acl
            assert "propagate" in acl

    def test_build_report_acls_propagate_display(self):
        by_path_ugid = {(a["path"], a["ugid"]): a for a in self.data["acls"]}
        assert by_path_ugid[("/", "admin@pam")]["propagate"] == "Yes"
        assert by_path_ugid[("/vms", "ops")]["propagate"] == "No"

    def test_build_report_groups_present(self):
        assert "groups" in self.data

    def test_build_report_groups_count(self):
        assert len(self.data["groups"]) == len(self.groups)

    def test_build_report_groups_fields(self):
        for group in self.data["groups"]:
            assert "groupid" in group
            assert "comment" in group
            assert "members" in group

    def test_build_report_groups_members_resolved(self):
        by_id = {g["groupid"]: g for g in self.data["groups"]}
        assert "admin@pam" in by_id["admins"]["members"]
        assert "bob@pve" in by_id["ops"]["members"]

    def test_build_report_groups_members_only_cluster_users(self):
        """Members listed must be users that exist in the cluster."""
        cluster_userids = {u["userid"] for u in self.data["users"]}
        for group in self.data["groups"]:
            if group["members"]:
                for member in group["members"].split(", "):
                    assert member in cluster_userids

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
            assert "tokens" in user

    def test_build_report_users_tokens(self):
        by_id = {u["userid"]: u for u in self.data["users"]}
        assert "admin@pam!ci-token" in by_id["admin@pam"]["tokens"]
        assert "admin@pam!backup-token" in by_id["admin@pam"]["tokens"]
        assert by_id["bob@pve"]["tokens"] == ""

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
        assert "## Access Control" in md
        assert "## Detailled ressources" in md
        assert "## Sanity Checks" in md
        assert "### Nodes" in md
        assert "### High Availability Groups" in md
        assert "### Backup Jobs" in md
        assert "### Virtual Machines" in md
        assert "### Storage" in md
        assert "### Users" in md
        assert "### Groups" in md
        assert "### Permissions" in md

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


class ReportWithHaRulesTestcase(PVEControlTestcase):
    """Tests for HA data using new Proxmox >= 9.1 rules API."""

    def _extra_fixtures(self):
        self.ha_rules = [
            fake_ha_rule("group-az1", ["pve-devel-1", "pve-devel-2"], [100, 101]),
            fake_ha_rule("group-az2", ["pve-devel-2"], [102]),
        ]

    def _extra_routes(self):
        self._register_full_routes()

    def _post_setup(self):
        _ = self.cluster.ha
        self.data = _build_report_data(self.cluster)

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
        assert "### High Availability Groups" in md
        assert "group-az1" in md
        assert "group-az2" in md


class ReportWithHaGroupsTestcase(PVEControlTestcase):
    """Tests for HA data using old Proxmox < 9.1 groups API (group field on resources)."""

    def _extra_fixtures(self):
        self.ha_resources = [
            fake_ha_resource(100, group="legacy-group"),
            fake_ha_resource(101, group="legacy-group"),
        ]

    def _extra_routes(self):
        self._register_full_routes()

    def _post_setup(self):
        _ = self.cluster.ha

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
