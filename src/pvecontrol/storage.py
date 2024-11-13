class PVEStorage:
  """Proxmox VE Storage"""

  _acceptable_kwargs = (
    'storage', 'shared', 'maxdisk', 'disk', 'plugintype', 'status'
  )

  def __init__(self, node, id, **kwargs):
    self.id = id
    self.node = node

    for k in kwargs.keys():
      if k in self._acceptable_kwargs:
        self.__setattr__(k, kwargs[k])

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
