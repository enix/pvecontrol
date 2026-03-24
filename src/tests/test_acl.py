import pytest

from pvecontrol.models.acl import PVEAcl


def test_basic_instantiation():
    acl = PVEAcl("/", "user", "admin@pam", "Administrator")
    assert acl.path == "/"
    assert acl.type == "user"
    assert acl.ugid == "admin@pam"
    assert acl.roleid == "Administrator"
    assert acl.propagate is False


def test_propagate_true():
    acl = PVEAcl("/", "user", "admin@pam", "Administrator", propagate=1)
    assert acl.propagate is True


def test_propagate_false():
    acl = PVEAcl("/", "user", "admin@pam", "Administrator", propagate=0)
    assert acl.propagate is False


def test_type_group():
    acl = PVEAcl("/vms", "group", "admins", "PVEVMAdmin")
    assert acl.type == "group"


def test_type_token():
    acl = PVEAcl("/", "token", "admin@pam!ci-token", "PVEAuditor")
    assert acl.type == "token"


def test_str():
    acl = PVEAcl("/", "user", "admin@pam", "Administrator")
    assert str(acl) == "PVEAcl(/, user, admin@pam, Administrator)"


def test_invalid_path_empty():
    with pytest.raises(ValueError, match="Invalid path"):
        PVEAcl("", "user", "admin@pam", "Administrator")


def test_invalid_path_none():
    with pytest.raises(ValueError, match="Invalid path"):
        PVEAcl(None, "user", "admin@pam", "Administrator")


def test_invalid_type():
    with pytest.raises(ValueError, match="Invalid type"):
        PVEAcl("/", "role", "admin@pam", "Administrator")


def test_invalid_ugid_empty():
    with pytest.raises(ValueError, match="Invalid ugid"):
        PVEAcl("/", "user", "", "Administrator")


def test_invalid_roleid_empty():
    with pytest.raises(ValueError, match="Invalid roleid"):
        PVEAcl("/", "user", "admin@pam", "")
