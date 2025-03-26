from pvecontrol.utils import reorder_keys


def test_reorder_keys():
    input_d = {"a": 1, "b": 2, "c": 3, "d": 4}
    keys = ["c", "a"]
    assert reorder_keys(input_d, keys) == {"c": 3, "a": 1, "b": 2, "d": 4}
