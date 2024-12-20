from pvecontrol.cluster import PVECluster
from pvecontrol.sanitycheck.checks import CheckCode
from pvecontrol.sanitycheck.tests import DEFAULT_CHECKS, DEFAULT_CHECK_IDS


class SanityCheck:

    def __init__(self, proxmox: PVECluster):
        self._proxmox = proxmox
        self._checks = []

    def run(self, checks):
        if not checks:
            checks = DEFAULT_CHECK_IDS

        for key in checks:
            check = DEFAULT_CHECKS[key](self._proxmox)
            check.run()
            self._checks.append(check)

        return self.get_exit_code()

    def get_exit_code(self):
        for check in self._checks:
            # exit early if most import code is found.
            if CheckCode.CRIT == check.status:
                return 1
        return 0

    def _get_longest_message(self):
        size = 0
        for check in self._checks:
            for msg in check.messages:
                size = max(size, len(msg))
        return size + 1

    def display(self):
        size = self._get_longest_message()
        current_type = None
        for check in self._checks:
            if current_type != check.type:
                current_type = check.type
                dash_size = int((size - (len(check.type.value) + 2)) / 2)
                print(f"{dash_size*'-'} {check.type.value} {dash_size*'-'}\n")
            check.display(size)
