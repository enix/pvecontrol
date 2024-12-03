from abc import ABC, abstractmethod
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
      status += msg.code

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
    print(f"{fonts.BOLD}{self.name}{fonts.END}\n")
    for msg in self.messages:
      msg.display(padding_max_size)
    print()
