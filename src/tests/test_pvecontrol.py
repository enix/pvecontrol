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
