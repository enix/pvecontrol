import json
import csv

from io import StringIO
from unittest.mock import Mock

import pytest
import yaml

from pvecontrol.models.vm import PVEVm, COLUMNS
from pvecontrol.utils import (
    format_row,
    match_filters,
    render_output,
    redact_secrets,
    run_auth_commands,
    parse_pve_version,
    OutputFormats,
)


def test_render_output():
    api = Mock()
    vms = [
        PVEVm(api, node="pve-node-1", vmid=100, status="running"),
        PVEVm(api, node="pve-node-1", vmid=101, status="running"),
        PVEVm(api, node="pve-node-2", vmid=102, status="stopped"),
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


def test_render_output_reads_models_through_their_attributes():
    vm = PVEVm(Mock(), node="pve-node-1", vmid=100, status="running", maxcpu=4)

    # cpus is not a dataclass field, it is computed from maxcpu
    rows = json.loads(render_output([vm], columns=["vmid", "cpus"], output=OutputFormats.JSON))

    assert rows == [{"vmid": 100, "cpus": 4}]


def _auth_config(**kwargs):
    clusterconfig = {
        "user": None,
        "password": None,
        "token_name": None,
        "token_value": None,
        "proxy_certificate": None,
    }
    clusterconfig.update(kwargs)
    return clusterconfig


def test_render_output_empty_table():
    # An empty list keeps its header, and the structured outputs are empty lists
    assert "| vmid | name |" in render_output([], columns=["vmid", "name"], sortby="vmid")
    assert json.loads(render_output([], columns=["vmid", "name"], output=OutputFormats.JSON)) == []
    assert yaml.safe_load(render_output([], columns=["vmid", "name"], output=OutputFormats.YAML)) == []
    assert render_output([], columns=["vmid", "name"], output=OutputFormats.CSV).strip() == "vmid,name"


def test_run_auth_commands_plain_values():
    auth = run_auth_commands(_auth_config(user="root@pam", password="secret"))
    assert auth == {"user": "root@pam", "password": "secret"}


def test_run_auth_commands_substitutes_token_as_str():
    auth = run_auth_commands(
        _auth_config(user="$(echo root@pam)", token_name="$(echo ci)", token_value="$(echo abcd-1234)")
    )
    assert auth == {"user": "root@pam", "token_name": "ci", "token_value": "abcd-1234"}
    assert all(isinstance(v, str) for v in auth.values())


def test_run_auth_commands_substitutes_password_as_str():
    auth = run_auth_commands(_auth_config(user="root@pam", password="$(echo secret)"))
    assert auth["password"] == "secret"


def test_run_auth_commands_proxy_certificate_from_command():
    cert = json.dumps({"cert": "/tmp/cert.pem", "key": "/tmp/key.pem"})
    auth = run_auth_commands(_auth_config(user="root@pam", proxy_certificate=f"$(echo '{cert}')"))
    assert auth["cert"] == ("/tmp/cert.pem", "/tmp/key.pem")
    assert "proxy_certificate" not in auth


def test_run_auth_commands_proxy_certificate_dict():
    auth = run_auth_commands(
        _auth_config(user="root@pam", proxy_certificate={"cert": "/tmp/cert.pem", "key": "/tmp/key.pem"})
    )
    assert auth["cert"] == ("/tmp/cert.pem", "/tmp/key.pem")


def test_run_auth_commands_password_and_token_conflict():
    with pytest.raises(SystemExit):
        run_auth_commands(_auth_config(user="root@pam", password="secret", token_name="ci", token_value="x"))


def test_run_auth_commands_token_name_without_value():
    with pytest.raises(SystemExit):
        run_auth_commands(_auth_config(user="root@pam", token_name="ci"))


def test_run_auth_commands_failing_command(caplog):
    with pytest.raises(SystemExit):
        run_auth_commands(_auth_config(user="root@pam", password="$(sh -c 'echo no secret key >&2; exit 2')"))
    assert "the command for password failed with exit status 2: no secret key" in caplog.text


def test_run_auth_commands_debug_log_masks_secrets(caplog):
    caplog.set_level("DEBUG")
    auth = run_auth_commands(_auth_config(user="ci@pve", token_name="ci", token_value="$(echo S3cretTok)"))
    assert auth["token_value"] == "S3cretTok"
    assert "S3cret" not in caplog.text
    assert "'token_name': 'ci'" in caplog.text


def test_redact_secrets():
    value = {
        "clusters": [{"name": "a", "password": "x", "token_value": None}, {"name": "b", "token_value": "y"}],
        "node": {"cpufactor": 2.5},
    }
    assert redact_secrets(value) == {
        "clusters": [{"name": "a", "password": "***", "token_value": None}, {"name": "b", "token_value": "***"}],
        "node": {"cpufactor": 2.5},
    }
    # The original is left untouched
    assert value["clusters"][0]["password"] == "x"


@pytest.mark.parametrize(
    "version, expected",
    [
        ("8.4", (8, 4)),
        ("9.0", (9, 0)),
        ("9.1", (9, 1)),
        ("9.2.4", (9, 2, 4)),
        ("9.10", (9, 10)),
        ("10.0", (10, 0)),
        ("9.0~beta1", (9, 0)),
        (" 9.1 ", (9, 1)),
    ],
)
def test_parse_pve_version(version, expected):
    assert parse_pve_version(version) == expected


def test_parse_pve_version_orders_like_versions():
    assert parse_pve_version("9.10") > parse_pve_version("9.2")
    assert parse_pve_version("10.0") > parse_pve_version("9.9")
    assert parse_pve_version("9.1") >= (9, 1)
    assert parse_pve_version("9.0") < (9, 1)


@pytest.mark.parametrize("version", ["", "beta", None])
def test_parse_pve_version_invalid(version):
    with pytest.raises(ValueError):
        parse_pve_version(version)


def test_format_row_sorts_sets():
    # The order of a set depends on the hash seed of the process, a filter must not
    row = format_row({"tags": {"web", "noevacuate", "prod"}})
    assert row["tags"] == ["noevacuate", "prod", "web"]
    assert match_filters(row, [("tags", r"^\['noevacuate', 'prod', 'web'\]$")])
