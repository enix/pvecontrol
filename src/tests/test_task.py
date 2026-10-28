import contextlib
import io

import pytest

import responses

from pvecontrol.models.task import TaskRunningStatus
from pvecontrol.utils import print_task
from tests.testcase import PVEControlTestcase

UPID_DONE = "UPID:pve-devel-1:0012F393:386532FE:6AE17182:aptupdate::root@pam:"
UPID_RUNNING = "UPID:pve-devel-2:000085CE:0006CBE0:6AE20FF0:qmstart:102:root@pam:"
UPID_NEW = "UPID:pve-devel-1:0000868F:0006CE40:6AE20FF6:qmstop:100:root@pam:"


class TaskListTestcase(PVEControlTestcase):
    """cluster/tasks holds the status of every task, as captured on PVE 9.2"""

    def _register_routes(self):
        super()._register_routes()
        self.responses_get(
            "/api2/json/cluster/tasks",
            data=[
                {
                    "upid": UPID_DONE,
                    "node": "pve-devel-1",
                    "type": "aptupdate",
                    "user": "root@pam",
                    "starttime": 1793159554,
                    "endtime": 1793159562,
                    "status": "OK",
                    "saved": "1",
                    "id": "",
                },
                {
                    "upid": UPID_RUNNING,
                    "node": "pve-devel-2",
                    "type": "qmstart",
                    "user": "root@pam",
                    "starttime": 1793200112,
                    "id": "102",
                },
            ],
        )
        # The status endpoint of a node gives no endtime
        self.responses_get(
            f"/api2/json/nodes/pve-devel-1/tasks/{UPID_NEW}/status",
            data={"status": "stopped", "exitstatus": "OK", "upid": UPID_NEW, "node": "pve-devel-1"},
        )
        self.responses_get(f"/api2/json/nodes/pve-devel-1/tasks/{UPID_NEW}/log", data=[{"n": 1, "t": "TASK OK"}])

    def _post_setup(self):
        start = len(responses.calls)
        self.tasks = {task.upid: task for task in self.cluster.tasks}
        self.list_calls = [c.request.url for c in responses.calls[start:]]

        start = len(responses.calls)
        with contextlib.redirect_stdout(io.StringIO()) as self.output:
            # Started a moment ago, not listed in cluster/tasks yet
            print_task(self.cluster, UPID_NEW)
        self.print_calls = [c.request.url for c in responses.calls[start:]]

        start = len(responses.calls)
        self.cluster.refresh()
        self.refresh_calls = [c.request.url for c in responses.calls[start:]]

    def test_list_in_one_call(self):
        assert [url.split("/api2/json")[1] for url in self.list_calls] == ["/cluster/tasks"]

    def test_list_status(self):
        done = self.tasks[UPID_DONE]
        assert done.runningstatus == TaskRunningStatus.STOPPED
        assert done.exitstatus == "OK"
        assert done.endtime == 1793159562
        assert self.tasks[UPID_RUNNING].runningstatus == TaskRunningStatus.RUNNING

    def test_get_task_from_its_node(self):
        # The task is fetched from its node, cluster/tasks is not needed
        assert not [url for url in self.print_calls if "/cluster/tasks" in url]
        assert any(f"/tasks/{UPID_NEW}/status" in url for url in self.print_calls)
        assert UPID_NEW in self.output.getvalue()

    def test_refresh_does_not_fetch_tasks(self):
        assert not [url for url in self.refresh_calls if "/tasks" in url]

    @responses.activate
    def test_task_not_found(self):
        self.responses_get("/api2/json/cluster/tasks", data=[])
        # Its node is not online (unknown here) and cluster/tasks doesn't list it
        with self.assertLogs(level="ERROR") as logs, pytest.raises(SystemExit) as exit_info:
            print_task(self.cluster, "UPID:pve-devel-9:00000001:00000001:6AE20FF6:qmstop:100:root@pam:")
        assert exit_info.value.code == 1
        assert "not found" in "\n".join(logs.output)
