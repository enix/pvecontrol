import json

import pytest
import requests
import responses

from proxmoxer.core import ResourceException

from pvecontrol.models.cluster import PVECluster

API = "https://pve.example.com:8006/api2/json"
TOKEN_AUTH = {"user": "ci@pve", "token_name": "pvecontrol", "token_value": "00000000-0000-0000-0000-000000000000"}


def _connect(**auth):
    return PVECluster("name", "pve.example.com", config={}, timeout=3, **(auth or TOKEN_AUTH))


@pytest.mark.parametrize(
    "error, expected",
    [
        (requests.exceptions.SSLError("certificate verify failed"), "TLS error with pve.example.com"),
        (requests.exceptions.ConnectTimeout("timed out"), "Connection to pve.example.com timed out after 3s"),
        (requests.exceptions.ReadTimeout("timed out"), "Connection to pve.example.com timed out after 3s"),
        (requests.exceptions.ConnectionError("Connection refused"), "Can't connect to pve.example.com"),
    ],
)
@responses.activate
def test_connection_errors(caplog, error, expected):
    # With a token, the first API call is the one that fails
    responses.get(f"{API}/version", body=error)
    with pytest.raises(SystemExit) as exit_info:
        _connect()
    assert exit_info.value.code == 1
    assert expected in caplog.text
    assert "Traceback" not in caplog.text


@responses.activate
def test_token_authentication_failure(caplog):
    responses.get(f"{API}/version", status=401)
    with pytest.raises(SystemExit):
        _connect()
    assert "Authentication failed on pve.example.com for ci@pve!pvecontrol" in caplog.text


@responses.activate
def test_password_authentication_failure(caplog):
    responses.post(f"{API}/access/ticket", status=401)
    with pytest.raises(SystemExit):
        _connect(user="ci@pve", password="wrong")
    assert "Authentication failed on pve.example.com for ci@pve" in caplog.text


@responses.activate
def test_password_connection_error(caplog):
    # With a password, ProxmoxAPI authenticates before any other call
    responses.post(f"{API}/access/ticket", body=requests.exceptions.ConnectionError("Connection refused"))
    with pytest.raises(SystemExit):
        _connect(user="ci@pve", password="secret")
    assert "Can't connect to pve.example.com" in caplog.text


@responses.activate
def test_other_api_errors_are_not_hidden():
    responses.get(f"{API}/version", status=500, body=json.dumps({"data": None}))
    with pytest.raises(ResourceException):
        _connect()
