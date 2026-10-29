import logging
from enum import Enum
from proxmoxer.tools import Tasks

from pvecontrol.utils import NODE_ERRORS, node_unreachable

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
        self._log_available = True

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
        if not self._log_available:
            return []
        try:
            return self._api.nodes(self.node).tasks(self.upid).log.get(limit=limit, start=start)
        except NODE_ERRORS as e:
            if not node_unreachable(e):
                raise
            # The status of the task stays as last read, only stop asking its node for the log
            logging.warning("Can't read the log of task %s, node %s can't be reached", self.upid, self.node)
            self._log_available = False
            return []

    def running(self):
        return self.runningstatus == TaskRunningStatus.RUNNING

    def vanished(self):
        return self.runningstatus == TaskRunningStatus.VANISHED

    def unknown(self):
        return self.runningstatus == TaskRunningStatus.UNKNOWN

    def refresh(self):
        try:
            status = self._api.nodes(self.node).tasks(self.upid).status.get()
        # Some task information can be vanished over time (tasks status files removed from the node filesystem)
        # In this case API return an error and we consider this tasks vanished and don't get more informations
        except NODE_ERRORS as e:
            # The node can't be reached, the task may still be running there
            if node_unreachable(e):
                self.runningstatus = TaskRunningStatus.UNKNOWN
        else:
            self.runningstatus = TaskRunningStatus[status.get("status", "stopped").upper()]
            self.endtime = status.get("endtime", 0)
            self.exitstatus = status.get("exitstatus", "")

    def decode_log(self, limit=0, start=0):
        log = self.log(limit, start)
        return Tasks.decode_log(log)
