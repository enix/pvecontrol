from enum import Enum
import proxmoxer.core
from proxmoxer.tools import Tasks

from pvecontrol.node import NodeStatus


class TaskRunningStatus(Enum):
  running = 0
  stopped = 1
  vanished = 2


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

    # This is bugguy. replace with a catch / except ?
    #    if self.node != NodeStatus.online:
    #      return
    try:
      status = self._api.nodes(self.node).tasks(self.upid).status.get()
    # Some task information can be vanished over time (tasks status files removed from the node filesystem)
    # In this case API return an error and we consider this tasks vanished and don't get more informations
    except proxmoxer.core.ResourceException:
      self.runningstatus = TaskRunningStatus["vanished"]
      self.endtime = 0
      self.exitstatus = "UNK"
    else:
      self.runningstatus = TaskRunningStatus[status.get("status", "stopped")]
      self.endtime = status.get("endtime", 0)
      self.exitstatus = status.get("exitstatus", "")

  def log(self, limit = 0, start = 0):
    return(self._api.nodes(self.node).tasks(self.upid).log.get(limit=limit, start=start))

  def running(self):
    return(self.runningstatus == TaskRunningStatus.running)

  def vanished(self):
    return(self.runningstatus == TaskRunningStatus.vanished)

  def refresh(self):
    self._initstatus()

  def decode_log(self, limit = 0, start = 0):
    log = self.log(limit, start)
    return(Tasks.decode_log(log))
