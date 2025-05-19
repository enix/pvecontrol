from abc import ABC, abstractmethod
from enum import Enum

from pvecontrol.utils import Fonts, terminal_support_utf_8, terminal_support_colors


class CheckType(Enum):
    HA = "HIGH_AVAILABILITY"
    NODE = "NODE"
    VM = "VIRTUAL_MACHINE"
    STORAGE = "STORAGE"


class CheckCode(Enum):
    CRIT = "CRITICAL"
    WARN = "WARNING"
    INFO = "INFO"
    OK = "OK"


ICONS_UTF8 = {
    CheckCode.CRIT.value: "❌",
    CheckCode.WARN.value: "⚠️",
    CheckCode.INFO.value: "ℹ️",
    CheckCode.OK.value: "✅",
}

ICONS_ASCII = {
    CheckCode.CRIT.value: "[CRIT]",
    CheckCode.WARN.value: "[WARN]",
    CheckCode.INFO.value: "[INFO]",
    CheckCode.OK.value: "[OK]",
}

ICONS_COLORED_ASCII = {
    CheckCode.CRIT.value: f"{Fonts.RED}[CRIT]{Fonts.END}",
    CheckCode.WARN.value: f"{Fonts.YELLOW}[WARN]{Fonts.END}",
    CheckCode.INFO.value: f"{Fonts.BLUE}[INFO]{Fonts.END}",
    CheckCode.OK.value: f"{Fonts.GREEN}[OK]{Fonts.END}",
}


def get_icons(colors=True, unicode=True):
    if unicode and terminal_support_utf_8():
        return ICONS_UTF8
    if colors and terminal_support_colors():
        return ICONS_COLORED_ASCII
    return ICONS_ASCII


class CheckMessage:
    def __init__(self, code: CheckCode, message):
        self.code = code
        self.message = message

    def display(self, padding_max_size, colors=True, unicode=True):
        icon = get_icons(colors, unicode)[self.code.value]
        padding = padding_max_size - len(self.message)
        msg = f"- {self.message}{padding * '.'}{icon}"
        print(msg)

    def __len__(self):
        return len(self.message)


class Check(ABC):

    type = ""
    name = ""

    def __init__(self, proxmox, messages=None, colors=True, unicode=True):
        if messages is None:
            messages = []
        self.proxmox = proxmox
        self.messages = messages
        self._colors = colors
        self._unicode = unicode

    @abstractmethod
    def run(self):
        pass

    @property
    def status(self):
        """Define status by the most import status in messages"""
        status = []
        for msg in self.messages:
            # exit early if most import code is found.
            if CheckCode.CRIT == msg.code:
                return CheckCode.CRIT
            status.append(msg.code)

        if CheckCode.WARN in status:
            return CheckCode.WARN

        if CheckCode.INFO in status:
            return CheckCode.INFO

        return CheckCode.OK

    def add_messages(self, messages):
        if isinstance(messages, CheckMessage):
            self.messages.append(messages)
        elif isinstance(messages, list):
            self.messages += messages

    def display(self, padding_max_size):
        if self._colors and terminal_support_colors():
            name = f"{Fonts.BOLD}{self.name}{Fonts.END}"
        else:
            name = f"{self.name}"
        print(f"{name}: {get_icons(self._colors, self._unicode)[self.status.value]}\n")

        for msg in self.messages:
            msg.display(padding_max_size, colors=self._colors, unicode=self._unicode)
        print()
