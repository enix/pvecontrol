import pvecontrol

def test_filter_keys():
  input = {'test': "toto", 'none': "noninclude"}
  filter = ["test"]
  assert pvecontrol._filter_keys(input, filter) == {'test': "toto"}
