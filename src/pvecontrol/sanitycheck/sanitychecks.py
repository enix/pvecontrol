from pvecontrol.cluster import PVECluster
from pvecontrol.sanitycheck.tests import DEFAULT_CHECKS, DEFAULT_CHECK_IDS


class SanityCheck():

    def __init__(self, proxmox: PVECluster):
      self._proxmox = proxmox
      self._checks = []

    def run(self, checks):
      if not checks:
        checks = DEFAULT_CHECK_IDS

      for check in checks:
        if not check in DEFAULT_CHECK_IDS:
          print(
            f"Sanity check '{check}' doesn't exists.\n"
            f"Here available values are:\n{', '.join(DEFAULT_CHECK_IDS)}"
          )
          return

      for id in checks:
        check = DEFAULT_CHECKS[id](self._proxmox)
        check.run()
        self._checks.append(check)

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
