import pytest

from pvecontrol.models.volume import PVEVolume
from tests.fixtures.api import fake_storage_content


def test_api_payload():
    payload = fake_storage_content("local", "vm-100-disk-0.qcow2", 100, "images", 1738461900, "qcow2", {})
    volume = PVEVolume.from_api(payload)

    assert volume.volid == "local:100/vm-100-disk-0.qcow2"
    assert volume.format == "qcow2"
    assert volume.size == 1124800
    assert volume.content == "images"
    assert volume.vmid == 100


def test_ctime_is_an_int():
    payload = fake_storage_content("local", "vm-100-disk-0.qcow2", 100, "images", 1738461900, "qcow2", {})
    payload["ctime"] = "1738461900"

    assert PVEVolume.from_api(payload).ctime == 1738461900


def test_from_api_ignores_unknown_keys():
    volume = PVEVolume.from_api({"volid": "local:100/disk.qcow2", "format": "qcow2", "something_new": "ignored"})

    assert volume.volid == "local:100/disk.qcow2"
    assert not hasattr(volume, "something_new")


def test_unknown_keys_are_rejected_outside_from_api():
    with pytest.raises(TypeError):
        PVEVolume(volid="local:100/disk.qcow2", something_new="ignored")


def test_str():
    output = str(PVEVolume(volid="local:100/disk.qcow2", format="qcow2", notes="a note"))

    assert output.startswith("Id: local:100/disk.qcow2\n")
    assert "Format: qcow2" in output
    assert "Notes: a note" in output
