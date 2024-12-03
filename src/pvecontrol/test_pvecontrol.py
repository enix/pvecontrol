from pvecontrol.utils import filter_keys


def testfilter_keys():
    input = {"test": "toto", "none": "noninclude"}
    filter = ["test"]
    assert filter_keys(input, filter) == {"test": "toto"}
