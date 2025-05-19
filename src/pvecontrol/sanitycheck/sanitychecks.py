from pvecontrol.models.cluster import PVECluster
from pvecontrol.sanitycheck.checks import CheckCode
from pvecontrol.sanitycheck.tests import DEFAULT_CHECKS, DEFAULT_CHECK_IDS


class SanityCheck:

    def __init__(self, proxmox: PVECluster, colors=True, unicode=True):
        self._proxmox = proxmox
        self._checks = []
        self._colors = colors
        self._unicode = unicode

    def run(self, checks):
        if not checks:
            checks = DEFAULT_CHECK_IDS

        for key in checks:
            check = DEFAULT_CHECKS[key](self._proxmox, colors=self._colors, unicode=self._unicode)
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

    def display_footer(self):
        title = "SUMMARY"
        size = self._get_longest_message()
        dash_size = int((size + 2 - len(title)) / 2)
        print(f"{dash_size*'-'} {title} {dash_size*'-'}\n")
        print(f"Total checks: {len(self._checks)}")
        print(f"Critical: {len([check for check in self._checks if check.status == CheckCode.CRIT])}")
        print(f"Warning: {len([check for check in self._checks if check.status == CheckCode.WARN])}")
        print(f"OK: {len([check for check in self._checks if check.status == CheckCode.OK])}")
        print(f"Info: {len([check for check in self._checks if check.status == CheckCode.INFO])}")

    def display(self):
        size = self._get_longest_message()
        current_type = None
        for check in self._checks:
            if current_type != check.type:
                current_type = check.type
                dash_size = int((size + 2 - len(check.type.value)) / 2)
                print(f"{dash_size*'-'} {check.type.value} {dash_size*'-'}\n")
            check.display(size)
        print("")
        self.display_footer()
