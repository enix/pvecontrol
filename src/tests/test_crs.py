import json
import logging
import unittest

from unittest.mock import patch
from urllib.parse import parse_qs

import responses

from click.testing import CliRunner

from pvecontrol import pvecontrol
from pvecontrol.models.crs import PVECrs
from tests.testcase import PVEControlTestcase

OPTIONS_URL = "https://host:8006/api2/json/cluster/options"
MANAGER_STATUS_URL = "https://host:8006/api2/json/cluster/ha/status/manager_status"


class PVECrsModelTestcase(unittest.TestCase):

    def test_defaults_when_absent(self):
        for value in [None, ""]:
            crs = PVECrs.from_api(value)
            assert crs.mode == "basic"
            assert crs.rebalance_on_start is False
            assert crs.auto_rebalance is False
            assert crs.threshold == 30
            assert crs.hold_duration == 3
            assert crs.margin == 10
            assert crs.method == "bruteforce"
            assert crs.to_property_string() == ""
            assert not crs.is_set("mode")

    def test_parse_object(self):
        crs = PVECrs.from_api({"ha": "static", "ha-auto-rebalance": 1, "ha-auto-rebalance-threshold": "25.5"})
        assert crs.mode == "static"
        assert crs.auto_rebalance is True
        assert crs.threshold == 25.5
        assert crs.margin == 10
        assert crs.is_set("threshold")
        assert not crs.is_set("margin")

    def test_dataclass_fields(self):
        # set keys land in the dataclass fields (kebab-case mapped to snake_case), unknown ones in extra
        crs = PVECrs.from_api({"ha": "static", "ha-auto-rebalance-margin": "15", "ha-future-key": "foo"})
        assert crs.ha == "static"
        assert crs.ha_auto_rebalance_margin == 15
        assert crs.ha_auto_rebalance is None
        assert crs.extra == {"ha-future-key": "foo"}

    def test_parse_property_string(self):
        crs = PVECrs.from_api("ha=dynamic, ha-rebalance-on-start=1,ha-auto-rebalance=0,ha-auto-rebalance-method=topsis")
        assert crs.mode == "dynamic"
        assert crs.rebalance_on_start is True
        assert crs.auto_rebalance is False
        assert crs.method == "topsis"

    def test_parse_default_key(self):
        assert PVECrs.from_api("static").mode == "static"

    def test_parse_booleans(self):
        for raw, expected in [(1, True), (0, False), ("1", True), ("0", False), (True, True), ("false", False)]:
            assert PVECrs.from_api({"ha-rebalance-on-start": raw}).rebalance_on_start is expected
        with self.assertRaises(ValueError):
            PVECrs.from_api({"ha-rebalance-on-start": "maybe"})

    def test_serialize_in_schema_order(self):
        crs = PVECrs.from_api({"ha-auto-rebalance-margin": 5.0, "ha-auto-rebalance": True, "ha": "static"})
        assert crs.to_property_string() == "ha=static,ha-auto-rebalance=1,ha-auto-rebalance-margin=5"

    def test_serialize_adds_required_auto_rebalance(self):
        # every ha-auto-rebalance-* key requires ha-auto-rebalance in the same string
        crs = PVECrs().update(threshold=20.0)
        assert crs.to_property_string() == "ha-auto-rebalance=0,ha-auto-rebalance-threshold=20"
        assert PVECrs().update(mode="static").to_property_string() == "ha=static"

    def test_unknown_keys_are_kept(self):
        crs = PVECrs.from_api("ha=static,ha-future-key=foo").update(rebalance_on_start=True)
        assert crs.to_property_string() == "ha=static,ha-rebalance-on-start=1,ha-future-key=foo"

    def test_update_ignores_none(self):
        crs = PVECrs.from_api("ha=static,ha-auto-rebalance=1").update(mode=None, auto_rebalance=False)
        assert crs.to_property_string() == "ha=static,ha-auto-rebalance=0"

    def test_validate(self):
        assert not PVECrs.from_api("ha=static,ha-auto-rebalance=1").validate()
        assert not PVECrs.from_api("ha=dynamic,ha-auto-rebalance=1").validate()
        assert not PVECrs.from_api("ha=basic,ha-auto-rebalance=0").validate()
        # basic is the default mode
        assert len(PVECrs.from_api("ha-auto-rebalance=1").validate()) == 1
        assert len(PVECrs.from_api("ha=basic,ha-auto-rebalance=1").validate()) == 1
        errors = PVECrs.from_api(
            "ha=unknown,ha-auto-rebalance-threshold=101,ha-auto-rebalance-hold-duration=-1,ha-auto-rebalance-method=x"
        ).validate()
        assert len(errors) == 4

    def test_rows(self):
        rows = PVECrs.from_api("ha=static").to_rows()
        assert rows[0] == {"option": "ha", "value": "static", "source": "configured"}
        assert rows[1] == {"option": "ha-rebalance-on-start", "value": False, "source": "default"}
        assert len(rows) == 7


class PVECrsCommandsTestcase(PVEControlTestcase):

    def _run(self, args, crs=None, imbalance=None, **kwargs):
        # Each run starts from a fresh API state: new routes, and settings read again
        responses.reset()
        self.cluster._crs = None  # pylint: disable=protected-access
        options = {"keyboard": "en-us"}
        if crs is not None:
            options["crs"] = crs
        responses.get(OPTIONS_URL, body=json.dumps({"data": options}))
        manager_status = {"manager_status": {"master_node": "pve-devel-1"}}
        if imbalance is not None:
            manager_status["manager_status"]["imbalance"] = imbalance
        responses.get(MANAGER_STATUS_URL, body=json.dumps({"data": manager_status}))
        responses.put(OPTIONS_URL, body=json.dumps({"data": None}))
        with (
            patch("pvecontrol.actions.crs.PVECluster.create_from_config", return_value=self.cluster),
            self.assertLogs(level="DEBUG") as logs,
        ):
            result = CliRunner().invoke(pvecontrol, ["-c", "name", *args], **kwargs)
        errors = [record.getMessage() for record in logs.records if record.levelno >= logging.ERROR]
        return result, errors

    @staticmethod
    def _puts():
        return [parse_qs(call.request.body) for call in responses.calls if call.request.method == "PUT"]

    @responses.activate
    def test_show_json(self):
        result, errors = self._run(["-o", "json", "crs", "show"], crs={"ha": "static"}, imbalance=0.1234)
        assert result.exit_code == 0, result.output
        assert not errors
        rows = json.loads(result.stdout)
        assert rows[0] == {"option": "ha", "value": "static", "source": "configured"}
        assert {"option": "ha-auto-rebalance-threshold", "value": 30, "source": "default"} in rows
        assert rows[-1] == {"option": "imbalance", "value": "12.3%", "source": "ha manager"}

    @responses.activate
    def test_show_without_crs_nor_imbalance(self):
        result, _ = self._run(["-o", "json", "crs", "show"])
        assert result.exit_code == 0, result.output
        rows = json.loads(result.stdout)
        assert len(rows) == 7
        assert all(row["source"] == "default" for row in rows)

    @responses.activate
    def test_show_text(self):
        result, _ = self._run(["crs", "show"], crs="ha=static,ha-auto-rebalance=1", imbalance=0.5)
        assert result.exit_code == 0, result.output
        assert "ha-auto-rebalance" in result.stdout
        assert "50.0%" in result.stdout

    @responses.activate
    def test_set_read_modify_write(self):
        result, errors = self._run(
            ["crs", "set", "--auto-rebalance", "--threshold", "20", "--force"],
            crs={"ha": "dynamic", "ha-rebalance-on-start": 1},
        )
        assert result.exit_code == 0, result.output
        assert not errors
        assert self._puts() == [
            {"crs": ["ha=dynamic,ha-rebalance-on-start=1,ha-auto-rebalance=1,ha-auto-rebalance-threshold=20"]}
        ]
        assert "CRS settings updated" in result.stdout

    @responses.activate
    def test_set_adds_required_auto_rebalance(self):
        result, _ = self._run(["crs", "set", "--margin", "5", "--force"], crs="ha=static")
        assert result.exit_code == 0, result.output
        assert self._puts() == [{"crs": ["ha=static,ha-auto-rebalance=0,ha-auto-rebalance-margin=5"]}]

    @responses.activate
    def test_set_refuses_auto_rebalance_in_basic_mode(self):
        for args, crs in [
            (["--auto-rebalance"], None),
            (["--auto-rebalance"], "ha=basic"),
            (["--mode", "basic"], "ha=static,ha-auto-rebalance=1"),
        ]:
            with self.subTest(args=args, crs=crs):
                result, errors = self._run(["crs", "set", *args, "--force"], crs=crs)
                assert result.exit_code == 1
                assert len(errors) == 1
                assert "requires the static or dynamic mode" in errors[0]
                assert not self._puts()

    @responses.activate
    def test_set_dry_run(self):
        result, _ = self._run(["crs", "set", "--mode", "static", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "New CRS settings: ha=static" in result.stdout
        assert "Dry run" in result.stdout
        assert not self._puts()

    @responses.activate
    def test_set_declined(self):
        result, errors = self._run(["crs", "set", "--mode", "static"], input="no\n")
        assert result.exit_code == 1
        assert errors == ["Aborting"]
        assert not self._puts()

    @responses.activate
    def test_set_confirmed(self):
        result, _ = self._run(["crs", "set", "--mode", "static"], input="yes\n")
        assert result.exit_code == 0, result.output
        assert self._puts() == [{"crs": ["ha=static"]}]

    @responses.activate
    def test_set_unchanged(self):
        result, _ = self._run(["crs", "set", "--mode", "static", "--force"], crs="ha=static")
        assert result.exit_code == 0, result.output
        assert "CRS settings unchanged" in result.stdout
        assert not self._puts()

    @responses.activate
    def test_reset(self):
        result, _ = self._run(["crs", "set", "--reset", "--force"], crs="ha=static,ha-auto-rebalance=1")
        assert result.exit_code == 0, result.output
        assert self._puts() == [{"delete": ["crs"]}]

    @responses.activate
    def test_reset_already_default(self):
        result, _ = self._run(["crs", "set", "--reset", "--force"])
        assert result.exit_code == 0, result.output
        assert "CRS settings unchanged" in result.stdout
        assert not self._puts()

    @responses.activate
    def test_set_usage_errors(self):
        for args in [[], ["--reset", "--mode", "static"]]:
            with self.subTest(args=args):
                result = CliRunner().invoke(pvecontrol, ["-c", "name", "crs", "set", *args])
                assert result.exit_code == 2
                assert not responses.calls

    @responses.activate
    def test_set_invalid_values(self):
        for args in [["--threshold", "101"], ["--hold-duration", "-1"], ["--method", "random"]]:
            with self.subTest(args=args):
                result = CliRunner().invoke(pvecontrol, ["-c", "name", "crs", "set", *args])
                assert result.exit_code == 2
                assert not responses.calls

    @responses.activate
    def test_api_errors(self):
        responses.get(OPTIONS_URL, status=403, body=json.dumps({"data": None}))
        with (
            patch("pvecontrol.actions.crs.PVECluster.create_from_config", return_value=self.cluster),
            self.assertLogs(level="ERROR") as logs,
        ):
            result = CliRunner().invoke(pvecontrol, ["-c", "name", "crs", "show"])
        assert result.exit_code == 1
        assert "Cannot read the CRS settings" in logs.output[0]

    @responses.activate
    def test_put_error(self):
        responses.get(OPTIONS_URL, body=json.dumps({"data": {}}))
        responses.put(OPTIONS_URL, status=500, body=json.dumps({"data": None}))
        with (
            patch("pvecontrol.actions.crs.PVECluster.create_from_config", return_value=self.cluster),
            self.assertLogs(level="ERROR") as logs,
        ):
            result = CliRunner().invoke(pvecontrol, ["-c", "name", "crs", "set", "--mode", "static", "--force"])
        assert result.exit_code == 1
        assert "Error writing the CRS settings" in logs.output[0]
