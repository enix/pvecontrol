from abc import ABC, abstractmethod
from curses import has_colors as terminal_support_colors
from enum import Enum

from pvecontrol.utils import fonts, teminal_support_utf_8

class CheckType(Enum):
  HA = 'HIGH_AVAILABILITY'
  Node = "NODE"

class CheckCode(Enum):
  CRIT = 'CRITICAL'
  WARN = 'WARNING'
  INFO = 'INFO'
  OK = 'OK'

ICONS_UTF8 = {
  CheckCode.CRIT.value: '❌',
  CheckCode.WARN.value: '⚠️',
  CheckCode.INFO.value: 'ℹ️',
  CheckCode.OK.value: '✅',
}

ICONS_ASCII = {
  CheckCode.CRIT.value: '[CRIT]',
  CheckCode.WARN.value: '[WARN]',
  CheckCode.INFO.value: '[INFO]',
  CheckCode.OK.value: '[OK]',
}

ICONS_COLORED_ASCII = {
  CheckCode.CRIT.value: f'{fonts.RED}[CRIT]{fonts.END}',
  CheckCode.WARN.value: f'{fonts.YELLOW}[WARN]{fonts.END}',
  CheckCode.INFO.value: f'{fonts.BLUE}[INFO]{fonts.END}',
  CheckCode.OK.value: f'{fonts.GREEN}[OK]{fonts.END}',
}

def set_icons():
  if teminal_support_utf_8():
    return ICONS_UTF8
  if terminal_support_colors():
    return ICONS_COLORED_ASCII
  return ICONS_ASCII

ICONS = set_icons()

class CheckMessage:
  def __init__(self, code: CheckCode, message):
    self.code = code
    self.message = message

  def display(self, padding_max_size):
    padding = padding_max_size - len(self.message)
    msg = f"{self.message}{padding * '.'}{ICONS[self.code.value]}"
    print(msg)

  def __len__(self):
    return len(self.message)

class Check(ABC):

  type = ""
  name = ""

  def __init__(self, proxmox, messages = None):
    if messages is None:
      messages = []
    self.proxmox = proxmox
    self.messages = messages

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

  def set_code(self, code: CheckCode):
    self.code = code

  def display(self, padding_max_size):
    if terminal_support_colors():
      name = f"{fonts.BOLD}{self.name}{fonts.END}\n"
    else:
      name = f"{self.name}\n"
    print(name)

    for msg in self.messages:
      msg.display(padding_max_size)
    print()
