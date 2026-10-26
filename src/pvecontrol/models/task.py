from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import proxmoxer.core
from proxmoxer.tools import Tasks

COLUMNS = [
    "upid",
    "exitstatus",
    "node",
    "type",
    "starttime",
    "endtime",
    "runningstatus",
]


class TaskRunningStatus(Enum):
    RUNNING = 0
    STOPPED = 1
    VANISHED = 2

    def __str__(self):
        return self.name.lower()


@dataclass
class PVETaskData:
    upid: str = field(default="")
    node: str = field(default="")
    starttime: int = field(default=0)
    type: str = field(default="")
    user: str = field(default="")
    runningstatus: Optional[TaskRunningStatus] = TaskRunningStatus.VANISHED
    endtime: int = field(default=0)
    exitstatus: str = field(default="UNK")


class PVETask(PVETaskData):
    """Proxmox VE Task"""

    _api = None

    def __init__(self, api, upid):
        task = Tasks.decode_upid(upid)
        super().__init__(
            upid=upid,
            node=task["node"],
            starttime=task["starttime"],
            type=task["type"],
            user=task["user"],
        )

        self._api = api
        self.refresh()

    def log(self, limit=0, start=0):
        return self._api.nodes(self.node).tasks(self.upid).log.get(limit=limit, start=start)

    def running(self):
        return self.runningstatus == TaskRunningStatus.RUNNING

    def vanished(self):
        return self.runningstatus == TaskRunningStatus.VANISHED

    def refresh(self):
        # This is bugguy. replace with a catch / except ?
        #    if self.node != NodeStatus.online:
        #      return
        try:
            status = self._api.nodes(self.node).tasks(self.upid).status.get()
        # Some task information can be vanished over time (tasks status files removed from the node filesystem)
        # In this case API return an error and we consider this tasks vanished and don't get more informations
        except proxmoxer.core.ResourceException:
            pass
        else:
            self.runningstatus = TaskRunningStatus[status.get("status", "stopped").upper()]
            self.endtime = status.get("endtime", 0)
            self.exitstatus = status.get("exitstatus", "")

    def decode_log(self, limit=0, start=0):
        log = self.log(limit, start)
        return Tasks.decode_log(log)
