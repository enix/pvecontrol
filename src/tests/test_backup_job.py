from pvecontrol.backup_job import PVEBackupJob
from pvecontrol.vm import PVEVm


def test_is_selection_matching():
    vms = [
        PVEVm(None, "node-0", 0, "running", {"pool": "pool-A"}),
        PVEVm(None, "node-1", 1, "running", {"pool": "pool-A"}),
        PVEVm(None, "node-0", 2, "running", {"pool": "pool-B"}),
        PVEVm(None, "node-1", 3, "running", {"pool": "pool-B"}),
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
