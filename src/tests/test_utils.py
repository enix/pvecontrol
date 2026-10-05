import json
import csv

from io import StringIO
from unittest.mock import Mock

import pytest
import yaml

from pvecontrol.models.vm import PVEVm, COLUMNS
from pvecontrol.utils import render_output, run_auth_commands, OutputFormats


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
    output_md = render_output(vms, columns=COLUMNS, output=OutputFormats.MARKDOWN)

    assert output_text.split("\n")[0].replace("+", "").replace("-", "") == ""
    assert len(json.loads(output_json)) == 3
    assert len(list(csv.DictReader(StringIO(output_csv)))) == 3
    assert len(yaml.safe_load(output_yaml)) == 3
    assert len(output_md.split("\n")) == 5


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
