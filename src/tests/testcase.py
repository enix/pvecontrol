import unittest
import json

from unittest.mock import patch

import responses

from tests.fixtures.api import (
    execute_route,
    fake_node,
    fake_vm,
    fake_backup_job,
    get_status,
    get_resources,
    get_node_resources,
    generate_vm_routes,
)
from pvecontrol.cluster import PVECluster


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

        self.generate_routes()
        self.responses_get = self.create_response_wrapper()

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

    def create_response_wrapper(self):

        def wrapper(path, data=None, **kwargs):
            kwargs["params"] = kwargs.get("params", {})
            url = "https://host:8006" + path

            if data is None:
                body = execute_route(self.routes, "GET", url, **kwargs)
            else:
                body = json.dumps({"data": data})

            responses.get(url, body=body)

        return wrapper

    def generate_routes(self):
        self.routes = {
            "/api2/json/cluster/status": get_status(self.nodes),
            "/api2/json/cluster/resources": get_resources(self.nodes, self.vms),
            "/api2/json/nodes": get_node_resources(self.nodes),
            "/api2/json/cluster/tasks": [],
            "/api2/json/cluster/ha/groups": [],
            "/api2/json/cluster/ha/status/manager_status": [],
            "/api2/json/cluster/ha/resources": [],
            "/api2/json/cluster/backup": self.backup_jobs,
            **generate_vm_routes(self.nodes, self.vms),
        }

        print("ROUTES:")
        for route_path in self.routes.keys():
            print(route_path)
        print("")
