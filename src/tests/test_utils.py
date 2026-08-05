import json
import csv

from io import StringIO
from unittest.mock import Mock

import yaml

from pvecontrol.models.vm import PVEVm, COLUMNS
from pvecontrol.utils import render_output, OutputFormats


def test_render_output():
    api = Mock()
    vms = [
        PVEVm(api=api, node="pve-node-1", vmid=100, status="running"),
        PVEVm(api=api, node="pve-node-2", vmid=101, status="running"),
        PVEVm(api=api, node="pve-node-3", vmid=102, status="running"),
    ]

    output_text = render_output(vms, columns=COLUMNS, output=OutputFormats.TEXT)
    output_json = render_output(vms, columns=COLUMNS, output=OutputFormats.JSON)
    output_csv = render_output(vms, columns=COLUMNS, output=OutputFormats.CSV)
    output_yaml = render_output(vms, columns=COLUMNS, output=OutputFormats.YAML)
    output_md = render_output(vms, columns=COLUMNS, output=OutputFormats.MARKDOWN)

    assert output_text.split("\n")[0].replace("+", "").replace("-", "") == ""
    assert len(json.loads(output_json)) == 3
    assert len(list(csv.DictReader(StringIO(output_csv)))) == 3
    assert len(yaml.safe_load(output_yaml)) == 3
    assert len(output_md.split("\n")) == 5
