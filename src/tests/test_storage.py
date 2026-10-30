import copy
import csv
import io
import json

from unittest.mock import patch

import yaml

from click.testing import CliRunner

from pvecontrol import pvecontrol
from pvecontrol.models.storage import COLUMNS, PVEStorage
from tests.fixtures.api import fake_storage_resource
from tests.testcase import PVEControlTestcase

GIB = 1024**3

EXPECTED_ROWS = [
    {
        "storage": "local",
        "nodes": "pve-devel-1",
        "shared": "local",
        "usage": "25.0%",
        "maxdisk": 100 * GIB,
        "disk": 25 * GIB,
        "plugintype": "dir",
        "status": "available",
    },
    {
        "storage": "local",
        "nodes": "pve-devel-2",
        "shared": "local",
        "usage": "50.0%",
        "maxdisk": 100 * GIB,
        "disk": 50 * GIB,
        "plugintype": "dir",
        "status": "available",
    },
    {
        "storage": "local",
        "nodes": "pve-devel-3",
        "shared": "local",
        "usage": "75.0%",
        "maxdisk": 100 * GIB,
        "disk": 75 * GIB,
        "plugintype": "dir",
        "status": "available",
    },
    {
        "storage": "s3",
        "nodes": "pve-devel-1, pve-devel-2, pve-devel-3",
        "shared": "shared",
        "usage": "0.0%",
        "maxdisk": 0,
        "disk": 0,
        "plugintype": "s3",
        "status": "available",
    },
]


def _humanized(value):
    return f"{value / GIB:.1f} GiB" if value else "0 Bytes"


# The size columns are humanized in every output format
EXPECTED_OUTPUT = [
    {**row, "maxdisk": _humanized(row["maxdisk"]), "disk": _humanized(row["disk"])} for row in EXPECTED_ROWS
]


class PVEStorageFlattenedListTestcase(PVEControlTestcase):
    """3 nodes sharing an s3 storage, each with its own local storage"""

    def _build_fixtures(self):
        super()._build_fixtures()
        for i, node in enumerate(self.nodes, start=1):
            local = fake_storage_resource("local", node["status"]["name"], shared=0, plugin_type="dir")
            local.update({"maxdisk": 100 * GIB, "disk": 25 * i * GIB})
            self.storage_resources.append(local)
            self.storages_contents[node["status"]["name"]]["local"] = []

    def _snapshot(self):
        return [
            (storage, {k: copy.copy(v) if isinstance(v, (dict, list)) else v for k, v in vars(storage).items()})
            for storage in self.cluster.storages
        ]

    def _rows(self):
        rows = PVEStorage.get_flattened_grouped_list(self.cluster)
        return sorted(rows, key=lambda row: (row["storage"], row["nodes"]))

    def _storage_list(self, output):
        with patch("pvecontrol.cli.PVECluster.create_from_config", return_value=self.cluster):
            result = CliRunner().invoke(pvecontrol, ["-c", "name", "-o", output, "storage", "list"])
        assert result.exit_code == 0, result.output
        return result.output

    def test_storage_objects_unchanged(self):
        before = self._snapshot()
        self._rows()
        for storage, attributes in before:
            assert vars(storage) == attributes
            assert storage.node == storage.id.split("/")[1]

    def test_rows(self):
        rows = self._rows()
        assert [{col: row[col] for col in COLUMNS} for row in rows] == EXPECTED_ROWS
        assert rows[-1]["id"] == "storage/pve-devel-1/s3"

    def test_rows_hold_no_private_key(self):
        for row in self._rows():
            # COLUMNS, the other fields read from cluster/resources and the id: no private attribute
            assert set(row) == {*COLUMNS, "test", "id"}
            assert not any(key.startswith("_") for key in row)

    def test_idempotent(self):
        assert self._rows() == self._rows()

    def test_grouped_list_and_backups_still_work(self):
        self._rows()
        grouped = PVEStorage.get_grouped_list(self.cluster)
        assert sorted(item["storage"].node for item in grouped) == [
            "pve-devel-1",
            "pve-devel-1",
            "pve-devel-2",
            "pve-devel-3",
        ]
        assert self.cluster.backups == []

    def test_storage_list_json(self):
        rows = json.loads(self._storage_list("json"))
        assert sorted(rows, key=lambda row: (row["storage"], row["nodes"])) == EXPECTED_OUTPUT

    def test_storage_list_yaml(self):
        rows = yaml.safe_load(self._storage_list("yaml"))
        assert sorted(rows, key=lambda row: (row["storage"], row["nodes"])) == EXPECTED_OUTPUT

    def test_storage_list_csv(self):
        rows = list(csv.DictReader(io.StringIO(self._storage_list("csv"))))
        assert list(rows[0]) == COLUMNS
        assert sorted(rows, key=lambda row: (row["storage"], row["nodes"])) == EXPECTED_OUTPUT

    def test_storage_list_text_and_markdown(self):
        for output in ["text", "md"]:
            text = self._storage_list(output)
            for row in EXPECTED_OUTPUT:
                assert all(str(value) in text for value in row.values()), output
            assert "_api" not in text and "short_id" not in text, output
