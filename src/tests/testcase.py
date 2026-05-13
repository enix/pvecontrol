import unittest

from unittest.mock import patch
from datetime import datetime, timedelta

import responses

from tests.fixtures.api import (
    create_response_wrapper,
    fake_node,
    fake_vm,
    fake_backup,
    fake_backup_job,
    fake_storage_resource,
)
from pvecontrol.models.cluster import PVECluster

# class BasePVEControlTestcase(unittest.TestCase):


class PVEControlTestcase(unittest.TestCase):

    @responses.activate
    def setUp(self):
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
        self.backup_jobs = [
            fake_backup_job(1, "100"),
            fake_backup_job(2, "101"),
            fake_backup_job(3, "102"),
        ]
        self.storage_resources = [fake_storage_resource("s3", n["status"]["name"]) for n in nodes]
        self.backups = [
            fake_backup("s3", 100, datetime.now() - timedelta(minutes=110)),
            fake_backup("s3", 101, datetime.now() - timedelta(minutes=90)),
        ]
        self.storages_contents = {node["status"]["name"]: {"s3": self.backups} for node in self.nodes}

        self.ha_rules = None
        self.ha_resources = None
        self.users = None
        self.groups = None
        self.acls = None
        self._extra_fixtures()

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

        self.responses_get("/api2/json/version")
        self.responses_get("/api2/json/cluster/status")
        self.responses_get("/api2/json/cluster/resources")
        for node in nodes:
            name = node["status"]["name"]
            self.responses_get(f"/api2/json/nodes/{name}/version")
            self.responses_get(f"/api2/json/nodes/{name}/qemu")
        self._extra_routes()

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
        self._post_setup()

    def _extra_fixtures(self):
        """Subclass hook to set self.ha_rules / users / groups / acls before the response wrapper is built."""

    def _extra_routes(self):
        """Subclass hook to register additional response routes."""

    def _post_setup(self):
        """Subclass hook called once self.cluster is built (response mock still active)."""

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

    def _register_full_routes(self):
        for vm in self.vms:
            self.responses_get(f"/api2/json/nodes/{vm['node']}/qemu/{vm['vmid']}/config")
        for node in self.nodes:
            name = node["status"]["name"]
            for storage in self.storage_resources:
                self.responses_get(
                    f"/api2/json/nodes/{name}/storage/{storage['storage']}/content",
                    params={"content": "backup"},
                )
        self.responses_get("/api2/json/cluster/ha/rules")
        self.responses_get("/api2/json/cluster/ha/status/manager_status")
        self.responses_get("/api2/json/cluster/ha/resources")
        self.responses_get("/api2/json/cluster/backup")
        self.responses_get("/api2/json/access/users")
        self.responses_get("/api2/json/access/groups")
        self.responses_get("/api2/json/access/acl")
