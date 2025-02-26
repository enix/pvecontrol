from pvecontrol.backup_job import PVEBackupJob
from pvecontrol.vm import PVEVm


def test_is_selection_matching():
    vms = [PVEVm(None, "node-" + str(id % 2), id, "running") for id in range(0, 4)]

    def check_is_selection_matching_array(truth_table, backup_job):
        for i, is_scheduled in enumerate(truth_table):
            assert backup_job.is_selection_matching(vms[i]) == bool(is_scheduled)

    check_is_selection_matching_array([1, 0, 0, 0], PVEBackupJob(0, vmid="0"))
    check_is_selection_matching_array([0, 0, 1, 1], PVEBackupJob(0, vmid="2,3"))
    check_is_selection_matching_array([1, 1, 1, 1], PVEBackupJob(0, all=1))
    check_is_selection_matching_array([1, 0, 0, 1], PVEBackupJob(0, all=1, exclude="1,2"))
    check_is_selection_matching_array([1, 0, 1, 0], PVEBackupJob(0, all=1, node="node-0"))
    check_is_selection_matching_array([1, 0, 0, 0], PVEBackupJob(0, all=1, node="node-0", exclude="2"))
