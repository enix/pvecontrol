import json
import csv

from io import StringIO
from unittest.mock import Mock

import yaml

from pvecontrol.vm import PVEVm, COLUMNS
from pvecontrol.utils import render_output, OutputFormats


def test_render_output():
    api = Mock()
    vms = [
        PVEVm(api, "pve-node-1", 100, "running"),
        PVEVm(api, "pve-node-1", 101, "running"),
        PVEVm(api, "pve-node-2", 102, "stopped"),
    ]

    output_text = render_output(vms, columns=COLUMNS, output=OutputFormats.TEXT)
    output_json = render_output(vms, columns=COLUMNS, output=OutputFormats.JSON)
    output_csv = render_output(vms, columns=COLUMNS, output=OutputFormats.CSV)
    output_yaml = render_output(vms, columns=COLUMNS, output=OutputFormats.YAML)

    assert output_text.split("\n")[0].replace("+", "").replace("-", "") == ""
    assert len(json.loads(output_json)) == 3
    assert len(list(csv.DictReader(StringIO(output_csv)))) == 3
    assert len(yaml.safe_load(output_yaml)) == 3
