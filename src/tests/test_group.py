import pytest

from pvecontrol.models.group import PVEGroup
from pvecontrol.models.user import PVEUser


def test_basic_instantiation():
    group = PVEGroup("admins")
    assert group.groupid == "admins"
    assert group.comment == ""
    assert group.users == []


def test_all_fields():
    group = PVEGroup("ops", comment="Operations team", users="alice@pam,bob@pve")
    assert group.groupid == "ops"
    assert group.comment == "Operations team"
    assert group.users == ["alice@pam", "bob@pve"]


def test_users_empty_string():
    group = PVEGroup("admins", users="")
    assert group.users == []


def test_users_single():
    group = PVEGroup("admins", users="alice@pam")
    assert group.users == ["alice@pam"]


def test_users_list_input():
    group = PVEGroup("admins", users=["alice@pam", "bob@pve"])
    assert group.users == ["alice@pam", "bob@pve"]


def test_str():
    group = PVEGroup("admins")
    assert str(group) == "PVEGroup(admins)"


def test_invalid_groupid_empty():
    with pytest.raises(ValueError, match="Invalid groupid"):
        PVEGroup("")


def test_invalid_groupid_none():
    with pytest.raises(ValueError, match="Invalid groupid"):
        PVEGroup(None)


class FakeCluster:
    def __init__(self, users, groups):
        self.users = users
        self.groups = groups


def test_get_members_returns_matching_users():
    alice = PVEUser("alice@pam")
    bob = PVEUser("bob@pve")
    carol = PVEUser("carol@pve")
    group = PVEGroup("admins", users="alice@pam,bob@pve")
    cluster = FakeCluster(users=[alice, bob, carol], groups=[group])

    members = group.get_members(cluster)
    assert alice in members
    assert bob in members
    assert carol not in members


def test_get_members_empty_group():
    alice = PVEUser("alice@pam")
    group = PVEGroup("empty")
    cluster = FakeCluster(users=[alice], groups=[group])

    assert group.get_members(cluster) == []


def test_get_members_user_not_in_cluster():
    group = PVEGroup("admins", users="ghost@pam")
    cluster = FakeCluster(users=[], groups=[group])

    assert group.get_members(cluster) == []


def test_user_get_groups_returns_matching_groups():
    alice = PVEUser("alice@pam", groups="admins,ops")
    admins = PVEGroup("admins", users="alice@pam")
    ops = PVEGroup("ops", users="alice@pam,bob@pve")
    devs = PVEGroup("devs")
    cluster = FakeCluster(users=[alice], groups=[admins, ops, devs])

    groups = alice.get_groups(cluster)
    assert admins in groups
    assert ops in groups
    assert devs not in groups


def test_user_get_groups_no_groups():
    alice = PVEUser("alice@pam")
    admins = PVEGroup("admins", users="bob@pve")
    cluster = FakeCluster(users=[alice], groups=[admins])

    assert alice.get_groups(cluster) == []


def test_get_members_and_get_groups_are_consistent():
    """A user that is a member of a group should also return that group via get_groups."""
    alice = PVEUser("alice@pam", groups="admins")
    admins = PVEGroup("admins", users="alice@pam")
    cluster = FakeCluster(users=[alice], groups=[admins])

    assert alice in admins.get_members(cluster)
    assert admins in alice.get_groups(cluster)
