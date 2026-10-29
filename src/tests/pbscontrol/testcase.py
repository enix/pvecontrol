import unittest

from unittest.mock import patch

import responses

from tests.pbscontrol.fixtures.api import create_response_wrapper, fake_datastore
from pbscontrol.models.server import PBSServer


class PBSControlTestcase(unittest.TestCase):

    @responses.activate
    def setUp(self):
        self.datastores = [
            fake_datastore("datastore1", total=1_000_000_000_000, used=400_000_000_000),
            fake_datastore("datastore2", total=2_000_000_000_000, used=1_800_000_000_000),
        ]

        self.responses_get = create_response_wrapper(self.datastores)

        self.responses_get("/api2/json/version")
        self.responses_get("/api2/json/admin/datastore")
        for ds in self.datastores:
            self.responses_get(f"/api2/json/admin/datastore/{ds['store']}/status")

        with patch("proxmoxer.backends.https.ProxmoxHTTPAuth") as mock_auth:
            mock_auth_instance = mock_auth.return_value
            mock_auth_instance.timeout = 1

            self.server = PBSServer(
                "test-pbs",
                "host",
                port=8007,
                verify_ssl=False,
                timeout=mock_auth_instance.timeout,
                **{"user": "root@pam", "password": "password"},
            )
