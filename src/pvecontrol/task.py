from enum import Enum
from proxmoxer.tools import Tasks

from pvecontrol.node import NodeStatus


class TaskRunningStatus(Enum):
  running = 0
  stopped = 1


class PVETask:
  """Proxmox VE Task"""

  _api = None

  def __init__(self, api, upid):
    task = Tasks.decode_upid(upid)

    self._api = api
    self.upid = upid
    self.node = task["node"]
    self.starttime = task["starttime"]
    self.type = task["type"]
    self.user = task["user"]

    self.runningstatus = TaskRunningStatus.stopped
    self.exitstatus = ""
    self.endtime = 0
    self.description = ""
    self._initstatus()

  def _initstatus(self):
# This is bugguy. replace with a catch / except ?
#    if self.node != NodeStatus.online:
#      return
    status = self._api.nodes(self.node).tasks(self.upid).status.get()
    for k in status:
      if k == "status":
        self.runningstatus = TaskRunningStatus[status["status"]]
      elif k == "endtime":
        self.endtime = status["endtime"]
      elif k == "exitstatus":
        self.exitstatus = status["exitstatus"]


  def log(self, limit = 0, start = 0):
    return(self._api.nodes(self.node).tasks(self.upid).log.get(limit=limit, start=start))

  def running(self):
    return(self.runningstatus == TaskRunningStatus.running)

  def refresh(self):
    self._initstatus()

  def decode_log(self, limit = 0, start = 0):
    log = self.log(limit, start)
    return(Tasks.decode_log(log))
