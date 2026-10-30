import unittest
from unittest.mock import patch

from pvecontrol.sanitycheck.checks import Check, CheckCode, CheckMessage, ICONS_COLORED_ASCII
from pvecontrol.utils import Fonts, terminal_support_colors


class FakeCheck(Check):
    id = "fake"
    name = "Fake check"

    def run(self):
        pass


class TerminalColorsTestcase(unittest.TestCase):
    """terminal_support_colors() initializes curses once per process, not once per message"""

    def setUp(self):
        terminal_support_colors.cache_clear()
        self.addCleanup(terminal_support_colors.cache_clear)
        curses_patcher = patch("pvecontrol.utils.curses")
        self.curses = curses_patcher.start()
        self.addCleanup(curses_patcher.stop)
        self.curses.has_colors.return_value = True
        self.curses.COLORS = 256
        # ASCII icons: the path that asks for color support on every message
        utf8_patcher = patch("pvecontrol.sanitycheck.checks.terminal_support_utf_8", return_value=False)
        utf8_patcher.start()
        self.addCleanup(utf8_patcher.stop)

    def _display_checks(self):
        messages = [CheckMessage(code, f"message {i}") for i, code in enumerate(list(CheckCode) * 25)]
        checks = [FakeCheck(None, messages=list(messages), colors=True, unicode=False) for _ in range(5)]
        with patch("builtins.print") as mock_print:
            for check in checks:
                check.display(40)
        return [call.args[0] for call in mock_print.call_args_list if call.args]

    def test_curses_initialized_once(self):
        lines = self._display_checks()

        self.assertEqual(self.curses.initscr.call_count, 1)
        self.assertEqual(self.curses.endwin.call_count, 1)
        # Colors are still rendered on every line
        self.assertEqual(sum(1 for line in lines if line.startswith(f"{Fonts.BOLD}{FakeCheck.name}")), 5)
        self.assertEqual(sum(1 for line in lines if line.endswith(ICONS_COLORED_ASCII[CheckCode.OK.value])), 5 * 25)

    def test_no_color_support_detected_once(self):
        self.curses.initscr.side_effect = Exception("no terminal")

        lines = self._display_checks()

        self.assertEqual(self.curses.initscr.call_count, 1)
        self.assertFalse(any(Fonts.END in line for line in lines))
        self.assertTrue(any(line.endswith("[CRIT]") for line in lines))
