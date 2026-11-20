import json
import logging

from dataclasses import dataclass, field
from typing import List
from unittest.mock import patch

from click.testing import CliRunner

from pvecontrol import pvecontrol
from pvecontrol.models import api_kwargs, format_fields
from pvecontrol.models.node import NodeStatus
from pvecontrol.models.task import TaskRunningStatus
from pvecontrol.models.vm import PVEVm, VmStatus
from tests.testcase import PVEControlTestcase


@dataclass
class SampleData:
    name: str = field(default="")
    next_run: int = field(default=0)
    items: List = field(default_factory=list)


def test_dashed_api_keys_are_mapped():
    assert api_kwargs(SampleData, {"next-run": 42}) == {"next_run": 42}


def test_default_factory_fields_are_kept():
    # those have no class attribute, a hasattr() based filter would drop them
    assert api_kwargs(SampleData, {"items": [1]}) == {"items": [1]}


def test_unknown_keys_are_dropped_and_logged(caplog):
    with caplog.at_level(logging.DEBUG):
        assert api_kwargs(SampleData, {"name": "a", "zzz": 1, "aaa": 2}) == {"name": "a"}

    assert "SampleData: ignoring api keys ['aaa', 'zzz']" in caplog.text


def test_format_fields():
    assert format_fields(SampleData(name="a", next_run=42)) == "Name: a\nNext-run: 42\nItems: []"


def test_format_fields_exclude():
    assert format_fields(SampleData(name="a", next_run=42), exclude=("name",)) == "Next-run: 42\nItems: []"


def test_models_compare_by_identity():
    # Models are mutable and get deduplicated through sets (node evacuate targets): they must stay hashable
    first = PVEVm(None, vmid=100, status="running")
    second = PVEVm(None, vmid=100, status="running")

    assert first != second
    assert len({first, second, first}) == 2


class StatusOutputTestcase(PVEControlTestcase):
    def _register_routes(self):
        super()._register_routes()
        self.responses_get(
            "/api2/json/cluster/tasks",
            data=[
                {
                    "upid": "UPID:pve-devel-1:0012F393:386532FE:6AE17182:aptupdate::root@pam:",
                    "node": "pve-devel-1",
                    "starttime": 1793159554,
                    "endtime": 1793159562,
                    "status": "OK",
                }
            ],
        )

    def _post_setup(self):
        # cluster/tasks and the HA status are read lazily, while the api is mocked
        _ = self.cluster.tasks
        _ = self.cluster.node_ha_states

    def _list(self, resource):
        with patch("pvecontrol.cli.PVECluster.create_from_config", return_value=self.cluster):
            result = CliRunner().invoke(pvecontrol, ["-c", "name", "-o", "json", resource, "list"])
        assert result.exit_code == 0, result.output
        return json.loads(result.output)

    def test_statuses_are_rendered_by_their_lowercase_name(self):
        assert {row["status"] for row in self._list("node")} == {"online"}
        assert {row["status"] for row in self._list("vm")} <= {"running", "stopped"}
        assert [row["runningstatus"] for row in self._list("task")] == ["stopped"]

    def test_enum_str(self):
        assert str(NodeStatus.ONLINE) == "online"
        assert str(VmStatus.RUNNING) == "running"
        assert str(TaskRunningStatus.STOPPED) == "stopped"
