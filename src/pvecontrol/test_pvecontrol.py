from pvecontrol.utils import filter_keys


def testfilter_keys():
    input_d = {"test": "toto", "none": "noninclude"}
    filter_k = ["test"]
    assert filter_keys(input_d, filter_k) == {"test": "toto"}
