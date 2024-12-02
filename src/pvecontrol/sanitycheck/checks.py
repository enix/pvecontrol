from enum import Enum

from pvecontrol.utils import fonts

class CheckType(Enum):
  HA = 'HIGHT_AVAILABILITY'
  Node = "NODE"

class CheckCode(Enum):
  CRIT = 'CRITICAL'
  WARN = 'WARNING'
  INFO = 'INFO'
  OK = 'OK'

ICONS = {
  CheckCode.CRIT.value: '❌',
  CheckCode.WARN.value: '⚠️',
  CheckCode.OK.value: '✅',
}

class CheckMessage:
  def __init__(self, code: CheckCode, message):
    self.code = code
    self.message = message

  def display(self, padding_max_size):
    padding = padding_max_size - len(self.message)
    print(f"{self.message}{padding * '.'}{ICONS[self.code.value]}")

  def __len__(self):
    return len(self.message)

class Check:

  def __init__(self, type: CheckType, name: str, messages = None):
    if messages is None:
      messages = []
    self.type = type
    self.name = name
    self.messages = messages

  def add_messages(self, messages):
    if isinstance(messages, CheckMessage):
      self.messages.append(messages)
    elif isinstance(messages, list):
      self.messages += messages

  def set_code(self, code: CheckCode):
    self.code = code

  def display(self, padding_max_size):
    print(f"{fonts.BOLD}{self.name}{fonts.END}\n")
    for msg in self.messages:
      msg.display(padding_max_size)
    print()
