from pvecontrol.utils import _filter_keys

def test_filter_keys():
  input = {'test': "toto", 'none': "noninclude"}
  filter = ["test"]
  assert _filter_keys(input, filter) == {'test': "toto"}
