import importlib

from pvecontrol.cluster import PVECluster


DEFAULT_CHECKS_ORDER = [
    'nodes',
    'ha_vms',
    'ha_groups',
]

class SanityCheck():

    def __init__(self, proxmox: PVECluster):
      self._proxmox = proxmox
      self._ha = self._proxmox.ha()
      self._checks = []

    def run(self, checks):
      if not checks:
        checks = DEFAULT_CHECKS_ORDER

      from . import tests
      pkgs = []
      for pkg_name in checks:
        pkg = None
        try:
          pkg = importlib.import_module(f"pvecontrol.sanitycheck.tests.{pkg_name}")
          pkgs.append(pkg)
        except ModuleNotFoundError:
          print(
            f"Sanity check '{pkg_name}' doesn't exists.\n"
            f"Here available values are:\n{', '.join(DEFAULT_CHECKS_ORDER)}"
          )
          return

      for pkg in pkgs:
        if pkg:
          method = getattr(pkg, 'get_checks')
          self._checks += method(self)

    def _get_longest_message(self):
      size = 0
      for check in self._checks:
        for msg in check.messages:
          if len(msg) > size:
            size = len(msg)
      return size + 1

    def display(self):
      size = self._get_longest_message()
      current_type = None
      for check in self._checks:
        if current_type != check.type:
          current_type = check.type
          dash_size = int((size - (len(check.type.value) + 2))/2)
          print(f"{dash_size*'-'} {check.type.value} {dash_size*'-'}\n")
        check.display(size)
