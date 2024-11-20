from enum import Enum


STORAGE_SHARED_ENUM = ['local', 'shared']
COLUMNS = ['storage', 'nodes', 'shared', 'usage', 'maxdisk', 'disk', 'plugintype', 'status']

class StorageShared(Enum):
  local = 0
  shared = 1

class PVEStorage:
  """Proxmox VE Storage"""

  _default_kwargs = {
    'storage': None,
    'maxdisk': None,
    'disk': None,
    'plugintype': None,
    'status': None,
    'test': None,
  }

  def __init__(self, node, id, shared, **kwargs):
    self.id = id
    self.node = node

    self.shared = STORAGE_SHARED_ENUM[shared]

    for k, v in self._default_kwargs.items():
        self.__setattr__(k, kwargs.get(k, v))

  @property
  def percentage(self):
    if self.maxdisk:
      return self.disk / self.maxdisk *100
    return 0

  def __str__(self):
    output = f"Node: {self.node}\n" + f"Id: {self.id}\n"
    for key in self._acceptable_kwargs:
      output += f"{key.capitalize()}: {self.__getattribute__(key)}\n"
    return output
