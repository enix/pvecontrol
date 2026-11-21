from pbscontrol import pbscontrol, get_leaf_command
from pbscontrol.actions.server import status


def test_get_leaf_command():
    testcases = [
        (pbscontrol, [], []),
        (pbscontrol, ["--debug"], ["--debug"]),
        (status, ["status"], []),
        (status, ["-o", "json", "status", "--help"], ["--help"]),
        (None, ["foobar"], []),
    ]

    for testcase in testcases:
        ctx = pbscontrol.make_context(pbscontrol.name, list(testcase[1]), resilient_parsing=True)
        leaf_cmd, leaf_args = get_leaf_command(pbscontrol, ctx, testcase[1])
        assert leaf_cmd == testcase[0]
        assert leaf_args == testcase[2]
