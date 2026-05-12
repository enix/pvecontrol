from unittest.mock import patch

from click.testing import CliRunner

from pvecontrol import pvecontrol, get_leaf_command
from pvecontrol.utils import reorder_keys
from pvecontrol.actions.node import root as node, evacuate
from pvecontrol.actions.vm import migrate


def test_reorder_keys():
    input_d = {"a": 1, "b": 2, "c": 3, "d": 4}
    keys = ["c", "a"]
    assert reorder_keys(input_d, keys) == {"c": 3, "a": 1, "b": 2, "d": 4}


def test_get_leaf_command():
    testcases = [
        (pvecontrol, [], []),
        (pvecontrol, ["--debug"], ["--debug"]),
        (node, ["node"], []),
        (evacuate, ["node", "evacuate"], []),
        (evacuate, ["-o", "json", "node", "evacuate", "--help"], ["--help"]),
        (migrate, ["vm", "migrate", "id", "target"], ["id", "target"]),
        (None, ["foobar"], []),
    ]

    for testcase in testcases:
        ctx = pvecontrol.make_context(pvecontrol.name, list(testcase[1]), resilient_parsing=True)
        leaf_cmd, leaf_args = get_leaf_command(pvecontrol, ctx, testcase[1])
        assert leaf_cmd == testcase[0]
        assert leaf_args == testcase[2]


@patch("pvecontrol.list_clusters", return_value=[])
def test_no_cluster_configured(_, caplog):
    result = CliRunner().invoke(pvecontrol, ["status"])
    assert result.exit_code == 1
    assert "No cluster configured" in caplog.text


@patch("pvecontrol.list_clusters", return_value=[])
def test_no_cluster_configured_shows_config_path(_, caplog):
    CliRunner().invoke(pvecontrol, ["status"])
    assert "Configuration file:" in caplog.text


@patch("pvecontrol.list_clusters", return_value=["prod", "staging"])
def test_multiple_clusters_lists_names(_, caplog):
    result = CliRunner().invoke(pvecontrol, ["status"])
    assert result.exit_code == 1
    assert "prod" in caplog.text
    assert "staging" in caplog.text


@patch("pvecontrol.list_clusters", return_value=["prod", "staging"])
def test_multiple_clusters_shows_usage_hint(_, caplog):
    CliRunner().invoke(pvecontrol, ["status"])
    assert "--cluster" in caplog.text


@patch("pvecontrol.actions.cluster.PVECluster.create_from_config")
@patch("pvecontrol.list_clusters", return_value=["prod"])
def test_auto_select_single_cluster(_, mock_create):
    CliRunner().invoke(pvecontrol, ["status"])
    mock_create.assert_called_once_with("prod")
