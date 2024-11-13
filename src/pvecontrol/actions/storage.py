from pvecontrol.utils import filter_keys, print_tableoutput


def action_storagelist(proxmox, args):
  """Describe cluster storages"""
  keys_to_order = ['storage', 'nodes', 'shared', 'usage', 'maxdisk', 'disk', 'plugintype', 'status']
  storages = {}
  for storage in proxmox.storages:
    d = storage.__dict__
    node = d.pop('node')
    value = {
      **d,
      'nodes': [],
      'usage': f"{storage.percentage:.1f}%"
    }
    if storage.shared:
      storages[storage.storage] = storages.get(storage.storage, value)
      storages[storage.storage]['nodes'] += [node]
    else:
      storages[storage.id] = value
      storages[storage.id]['nodes'] += [node]

  for id, storage in storages.items():
    storages[id]['nodes'] = ', '.join(storages[id]['nodes'])

  output = [ filter_keys(n, keys_to_order) for n in storages.values()]
  print_tableoutput(output, sortby='storage')
