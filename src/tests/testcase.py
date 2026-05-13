import unittest

from unittest.mock import patch

import responses

from tests.fixtures.api import (
    create_response_wrapper,
    fake_node,
    fake_vm,
    fake_storage_resource,
)
from pvecontrol.models.cluster import PVECluster


class PVEEmptyClusterTestcase(unittest.TestCase):
    """mock_auth + base routes only. Cluster is built with no nodes / vms / etc."""

    @responses.activate
    def setUp(self):
        self.nodes = []
        self.vms = []
        self.backup_jobs = []
        self.storage_resources = []
        self.backups = []
        self.storages_contents = {}
        self.ha_rules = None
        self.ha_resources = None
        self.users = None
        self.groups = None
        self.acls = None

        self._build_fixtures()
        self._build_wrapper()
        self._register_routes()
        self._build_cluster()
        self._post_setup()

    def _build_fixtures(self):
        """Subclass hook called before self._build_wrapper"""

    def _build_wrapper(self):
        self.responses_get = create_response_wrapper(
            nodes=self.nodes,
            vms=self.vms,
            backup_jobs=self.backup_jobs,
            storage_resources=self.storage_resources,
            storages_contents=self.storages_contents,
            ha_rules=self.ha_rules,
            ha_resources=self.ha_resources,
            users=self.users,
            groups=self.groups,
            acls=self.acls,
        )

    def _register_routes(self):
        self.responses_get("/api2/json/version")
        self.responses_get("/api2/json/cluster/status")
        self.responses_get("/api2/json/cluster/resources")

    def _build_cluster(self):
        with patch("proxmoxer.backends.https.ProxmoxHTTPAuth") as mock_auth:
            mock_auth_instance = mock_auth.return_value
            mock_auth_instance.timeout = 1

            self.cluster = PVECluster(
                "name",
                "host",
                config=self._cluster_config(),
                verify_ssl=False,
                **{"user": "user", "password": "password"},
                timeout=mock_auth_instance.timeout,
            )

    def _cluster_config(self):
        return {
            "node": {
                "cpufactor": 2.5,
                "memoryminimum": 81928589934592,
            },
            "vm": {
                "max_last_backup": 100,
            },
        }

    def _post_setup(self):
        """Subclass hook called once self.cluster is built (response mock still active)."""


class PVEControlTestcase(PVEEmptyClusterTestcase):
    """Base mock + nodes and vms"""

    def _build_fixtures(self):
        super()._build_fixtures()
        nodes = [
            fake_node(1, True),
            fake_node(2, True),
            fake_node(3, True),
        ]
        self.nodes = nodes
        self.vms = [
            fake_vm(100, nodes[0]),
            fake_vm(101, nodes[0]),
            fake_vm(102, nodes[1]),
            fake_vm(103, nodes[1]),
            fake_vm(104, nodes[1]),
        ]
        self.storage_resources = [fake_storage_resource("s3", n["status"]["name"]) for n in self.nodes]
        self.storages_contents = {node["status"]["name"]: {"s3": self.backups} for node in self.nodes}

    def _register_routes(self):
        super()._register_routes()

        for node in self.nodes:
            name = node["status"]["name"]
            self.responses_get(f"/api2/json/nodes/{name}/version")
            self.responses_get(f"/api2/json/nodes/{name}/qemu")
            for storage in self.storage_resources:
                self.responses_get(
                    f"/api2/json/nodes/{name}/storage/{storage['storage']}/content",
                    params={"content": "backup"},
                )

        for vm in self.vms:
            self.responses_get(f"/api2/json/nodes/{vm['node']}/qemu/{vm['vmid']}/config")

        self.responses_get("/api2/json/cluster/ha/rules")
        self.responses_get("/api2/json/cluster/ha/status/manager_status")
        self.responses_get("/api2/json/cluster/ha/resources")
        self.responses_get("/api2/json/cluster/backup")
        self.responses_get("/api2/json/access/users")
        self.responses_get("/api2/json/access/groups")
        self.responses_get("/api2/json/access/acl")
