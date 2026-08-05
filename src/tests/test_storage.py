from unittest.mock import Mock

from pvecontrol.models.storage import PVEStorage, StorageShared
from tests.fixtures.api import fake_storage_resource


def test_api_payload():
    payload = fake_storage_resource("local", "pve-node-1", shared=0, plugin_type="lvm")
    storage = PVEStorage(Mock(), **payload)

    assert storage.id == "storage/pve-node-1/local"
    assert storage.short_id == "local"
    assert storage.node == "pve-node-1"
    assert storage.storage == "local"
    assert storage.plugintype == "lvm"
    assert storage.maxdisk == 33601372160
    # the api object must not end up in the rendered attributes
    assert "api" not in storage.__dict__


def test_shared_is_an_enum():
    local = PVEStorage(Mock(), **fake_storage_resource("local", "pve-node-1", shared=0, plugin_type="lvm"))
    shared = PVEStorage(Mock(), **fake_storage_resource("shared", "pve-node-1", shared=1, plugin_type="lvm"))

    assert local.shared == StorageShared.LOCAL
    assert shared.shared == StorageShared.SHARED
    # rendered outputs keep the historical "local"/"shared" wording
    assert str(local.shared) == "local"
    assert str(shared.shared) == "shared"


def test_s3_sizing_is_ignored():
    storage = PVEStorage(Mock(), **fake_storage_resource("s3", "pve-node-1", plugin_type="s3"))

    assert storage.disk == 0
    assert storage.maxdisk == 0


def test_unknown_api_keys_are_ignored():
    payload = fake_storage_resource("local", "pve-node-1")
    payload["something_new"] = "ignored"

    assert not hasattr(PVEStorage(Mock(), **payload), "something_new")
