from enum import Enum
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
    UNKNOWN = 3


class PVETask:
    """Proxmox VE Task"""

    _api = None

    def __init__(self, api, upid, summary=None):
        """summary: the cluster/tasks entry of this task, used instead of fetching the status from its node"""
        task = Tasks.decode_upid(upid)

        self._api = api
        self.upid = upid
        self.node = task["node"]
        self.starttime = task["starttime"]
        self.type = task["type"]
        self.user = task["user"]
        self.runningstatus = TaskRunningStatus.VANISHED
        self.endtime = 0
        self.exitstatus = "UNK"

        if summary is None:
            self.refresh()
        elif "endtime" in summary:
            # In cluster/tasks, "status" holds the exit status of a finished task
            self.runningstatus = TaskRunningStatus.STOPPED
            self.endtime = summary["endtime"]
            self.exitstatus = summary.get("status", "")
        else:
            self.runningstatus = TaskRunningStatus.UNKNOWN

    def log(self, limit=0, start=0):
        return self._api.nodes(self.node).tasks(self.upid).log.get(limit=limit, start=start)

    def running(self):
        return self.runningstatus == TaskRunningStatus.RUNNING

    def vanished(self):
        return self.runningstatus == TaskRunningStatus.VANISHED

    def refresh(self):
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
