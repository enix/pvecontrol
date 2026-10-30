import contextlib
import io
from unittest import TestCase
from unittest.mock import patch

from pvecontrol.sanitycheck import SanityCheck
from pvecontrol.sanitycheck.checks import CheckType
from pvecontrol.sanitycheck.tests import DEFAULT_CHECKS, DEFAULT_CHECK_IDS


class SanityCheckOrderTestcase(TestCase):
    """The selected checks run and render in the canonical order of DEFAULT_CHECKS"""

    def setUp(self):
        # Stub every check to record the order they run in: this tests the ordering, not the checks themselves
        self.ran = []
        stack = contextlib.ExitStack()
        for check_class in DEFAULT_CHECKS.values():
            stack.enter_context(patch.object(check_class, "run", lambda check: self.ran.append(check.id)))
        self.addCleanup(stack.close)

    def _run(self, checks):
        self.ran = []
        sc = SanityCheck(None, colors=False, unicode=False)
        exitcode = sc.run(checks=checks)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sc.display()
        return self.ran, exitcode, buf.getvalue()

    @staticmethod
    def _banners(output):
        values = {check_type.value for check_type in CheckType}
        # A banner is "--- TYPE ---", the dashes depend on the longest message (none here)
        return [line.strip("- ") for line in output.splitlines() if line.strip("- ") in values]

    def test_default_checks_are_grouped_by_type(self):
        types = [check_class.type for check_class in DEFAULT_CHECKS.values()]
        grouped = [t for i, t in enumerate(types) if i == 0 or types[i - 1] != t]
        self.assertEqual(len(grouped), len(set(grouped)), "checks of a same type must be contiguous in DEFAULT_CHECKS")

    def test_scrambled_ids_with_duplicates(self):
        checks = ("disk_unused", "ha_vms", "nodes", "vms_start_on_boot", "ha_groups", "ha_vms", "disk_unused")
        ran, exitcode, output = self._run(checks)

        self.assertEqual(exitcode, 0)
        self.assertEqual(ran, ["nodes", "ha_groups", "ha_vms", "vms_start_on_boot", "disk_unused"])
        self.assertEqual(self._banners(output), ["NODE", "HIGH_AVAILABILITY", "VIRTUAL_MACHINE", "STORAGE"])

    def test_order_does_not_depend_on_input_order(self):
        _, _, output = self._run(("vms_start_on_boot", "ha_groups", "nodes", "ha_vms"))
        _, _, reversed_output = self._run(("ha_vms", "nodes", "ha_groups", "vms_start_on_boot"))
        self.assertEqual(output, reversed_output)
        self.assertEqual(self._banners(output), ["NODE", "HIGH_AVAILABILITY", "VIRTUAL_MACHINE"])

    def test_all_checks_when_none_given(self):
        for checks in ((), None, DEFAULT_CHECK_IDS):
            ran, _, output = self._run(checks)
            self.assertEqual(ran, list(DEFAULT_CHECK_IDS))
            banners = self._banners(output)
            self.assertEqual(len(banners), len(set(banners)))
            self.assertEqual(set(banners), {check_type.value for check_type in CheckType})

    def test_unknown_check_id(self):
        with self.assertRaises(ValueError):
            SanityCheck(None).run(checks=("nodes", "not_a_check"))
