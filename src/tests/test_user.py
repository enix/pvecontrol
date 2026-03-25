import pytest

from pvecontrol.models.user import PVEUser


def test_basic_instantiation():
    user = PVEUser("admin@pam")
    assert user.userid == "admin@pam"
    assert user.enable is True
    assert user.expire == 0
    assert user.firstname == ""
    assert user.lastname == ""
    assert user.email == ""
    assert user.realm_type == ""
    assert user.groups == []
    assert user.tokens == []


def test_all_fields():
    user = PVEUser(
        "bob@pve",
        enable=1,
        expire=1900000000,
        firstname="Bob",
        lastname="Builder",
        email="bob@example.com",
        **{"realm_type": "pve"},
        groups="ops,devs",
    )
    assert user.userid == "bob@pve"
    assert user.enable is True
    assert user.expire == 1900000000
    assert user.firstname == "Bob"
    assert user.lastname == "Builder"
    assert user.email == "bob@example.com"
    assert user.realm_type == "pve"
    assert user.groups == ["ops", "devs"]


def test_enable_false():
    user = PVEUser("carol@pam", enable=0)
    assert user.enable is False


def test_groups_empty_string():
    user = PVEUser("admin@pam", groups="")
    assert user.groups == []


def test_groups_single():
    user = PVEUser("admin@pam", groups="admins")
    assert user.groups == ["admins"]


def test_groups_list_input():
    user = PVEUser("admin@pam", groups=["admins", "ops"])
    assert user.groups == ["admins", "ops"]


def test_str():
    user = PVEUser("admin@pam")
    assert str(user) == "PVEUser(admin@pam)"


def test_invalid_userid_no_realm():
    with pytest.raises(ValueError, match="Invalid userid"):
        PVEUser("adminpam")


def test_invalid_userid_empty():
    with pytest.raises(ValueError, match="Invalid userid"):
        PVEUser("")


def test_invalid_enable_value():
    with pytest.raises(ValueError, match="Invalid enable value"):
        PVEUser("admin@pam", enable=2)


def test_invalid_expire_negative():
    with pytest.raises(ValueError, match="Invalid expire value"):
        PVEUser("admin@pam", expire=-1)


def test_invalid_expire_string():
    with pytest.raises(ValueError, match="Invalid expire value"):
        PVEUser("admin@pam", expire="never")


def test_tokens_from_list():
    user = PVEUser(
        "admin@pam",
        tokens=[
            {"tokenid": "mytoken", "expire": 0, "privsep": 1},
            {"tokenid": "citoken", "expire": 0, "privsep": 0},
        ],
    )
    assert "admin@pam!mytoken" in user.tokens
    assert "admin@pam!citoken" in user.tokens
    assert len(user.tokens) == 2


def test_tokens_empty_list():
    user = PVEUser("admin@pam", tokens=[])
    assert user.tokens == []


def test_tokens_absent():
    user = PVEUser("admin@pam")
    assert user.tokens == []
