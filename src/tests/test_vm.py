import json

from types import SimpleNamespace
from unittest.mock import patch

import responses

from click.testing import CliRunner

from pvecontrol.actions.vm import unlock
from pvecontrol.utils import OutputFormats
from tests.testcase import PVEControlTestcase


class PVEVmUnlockTestcase(PVEControlTestcase):

    def _build_fixtures(self):
        super()._build_fixtures()
        # vm 100 runs on pve-devel-1 and is locked
        self.vms[0]["lock"] = "backup"

    def _invoke(self, args):
        with patch("pvecontrol.actions.vm.PVECluster.create_from_config", return_value=self.cluster):
            obj = {"args": SimpleNamespace(cluster="name", output=OutputFormats.TEXT)}
            return CliRunner().invoke(unlock, args, obj=obj)

    @responses.activate
    def test_unlock(self):
        responses.put(
            "https://host:8006/api2/json/nodes/pve-devel-1/qemu/100/config",
            body=json.dumps({"data": None}),
        )

        result = self._invoke(["100"])

        assert result.exit_code == 0
        assert "Lock 'backup' removed from vm 100" in result.output
        assert len(responses.calls) == 1
        body = responses.calls[0].request.body
        assert "delete=lock" in body
        assert "skiplock=1" in body

    @responses.activate
    def test_unlock_not_locked(self):
        result = self._invoke(["101"])

        assert result.exit_code == 0
        assert "Vm 101 is not locked" in result.output
        assert len(responses.calls) == 0

    @responses.activate
    def test_unlock_unknown_vm(self):
        result = self._invoke(["999"])

        assert result.exit_code == 1
        assert "Vm not found" in result.output
        assert len(responses.calls) == 0

    @responses.activate
    def test_unlock_dry_run(self):
        result = self._invoke(["100", "--dry-run"])

        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert len(responses.calls) == 0
