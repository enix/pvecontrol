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

        self.responses_get = create_response_wrapper(
            self.nodes, self.vms, self.backup_jobs, self.storage_resources, self.storages_contents
        )

        self.responses_get("/api2/json/cluster/status")
        self.responses_get("/api2/json/cluster/resources")

        with patch("proxmoxer.backends.https.ProxmoxHTTPAuth") as mock_auth:
            mock_auth_instance = mock_auth.return_value
            mock_auth_instance.timeout = 1

            self.cluster = PVECluster(
                "name",
                "host",
                config={
                    "node": {
                        "cpufactor": 2.5,
                        "memoryminimum": 81928589934592,
                    },
                    "vm": {
                        "max_last_backup": 100,
                    },
                },
                verify_ssl=False,
                **{"user": "user", "password": "password"},
                timeout=mock_auth_instance.timeout,
            )
