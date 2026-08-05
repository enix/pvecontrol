from pvecontrol.models.backup_job import PVEBackupJob
from pvecontrol.models.vm import PVEVm
from tests.fixtures.api import fake_backup_job


def test_api_payload():
    payload = fake_backup_job(1, "100,101")
    backup_job = PVEBackupJob(payload.pop("id"), **payload)

    # the api uses dashes in those keys, they must not be dropped on the way in
    assert backup_job.next_run == 1735430400
    assert backup_job.notes_template == "{{guestname}}"
    assert backup_job.prune_backups == {"keep-last": "3"}

    assert backup_job.storage == "local"
    assert backup_job.vmid == ["100", "101"]
    assert backup_job.all is False


def test_is_selection_matching():
    vms = [
        PVEVm(None, node="node-0", vmid=0, status="running", pool="pool-A"),
        PVEVm(None, node="node-1", vmid=1, status="running", pool="pool-A"),
        PVEVm(None, node="node-0", vmid=2, status="running", pool="pool-B"),
        PVEVm(None, node="node-1", vmid=3, status="running", pool="pool-B"),
    ]

    def check_is_selection_matching_array(truth_table, backup_job):
        for i, is_scheduled in enumerate(truth_table):
            assert backup_job.is_selection_matching(vms[i]) == bool(is_scheduled)

    check_is_selection_matching_array([1, 0, 0, 0], PVEBackupJob(0, vmid="0"))
    check_is_selection_matching_array([0, 0, 1, 1], PVEBackupJob(0, vmid="2,3"))
    check_is_selection_matching_array([1, 1, 1, 1], PVEBackupJob(0, all=1))
    check_is_selection_matching_array([1, 0, 0, 1], PVEBackupJob(0, all=1, exclude="1,2"))
    check_is_selection_matching_array([1, 0, 1, 0], PVEBackupJob(0, all=1, node="node-0"))
    check_is_selection_matching_array([1, 0, 0, 0], PVEBackupJob(0, all=1, node="node-0", exclude="2"))
    check_is_selection_matching_array([1, 1, 0, 0], PVEBackupJob(0, pool="pool-A"))
    check_is_selection_matching_array([0, 0, 1, 0], PVEBackupJob(0, pool="pool-B", node="node-0"))
