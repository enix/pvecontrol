from unittest.mock import patch

import responses

from pvecontrol.sanitycheck.tests.vm_backups import VmBackups
from pvecontrol.sanitycheck import SanityCheck
from pvecontrol.sanitycheck.checks import CheckCode
from tests.sanitycheck.utils import assert_message
from tests.testcase import PVEControlTestcase


class PVEClusterTestcase(PVEControlTestcase):

    @responses.activate
    def test_check(self):
        self.responses_get("/api2/json/cluster/backup")
        self.responses_get("/api2/json/nodes/pve-devel-1/storage/s3/content", params={"content": "backup"})

        vm_backups_check = VmBackups(self.cluster)
        vm_backups_check.run()

        sc = SanityCheck(self.cluster)
        with patch.object(sc, "_checks", new=[vm_backups_check]):
            exitcode = sc.get_exit_code()
            sc.display()

            assert exitcode == 1
            assert len(vm_backups_check.messages) == 8

            # check for associated backup jobs
            assert_message(vm_backups_check.messages[0], CheckCode.OK, "vm-100", "is associated")
            assert_message(vm_backups_check.messages[1], CheckCode.OK, "vm-101", "is associated")
            assert_message(vm_backups_check.messages[2], CheckCode.OK, "vm-102", "is associated")
            assert_message(vm_backups_check.messages[3], CheckCode.WARN, "vm-103", "not associated")
            assert_message(vm_backups_check.messages[4], CheckCode.WARN, "vm-104", "not associated")

            # check for recent backups
            assert_message(vm_backups_check.messages[5], CheckCode.CRIT, "vm-100", "is too old")
            assert_message(vm_backups_check.messages[6], CheckCode.OK, "vm-101", "is recent enough")
            assert_message(vm_backups_check.messages[7], CheckCode.WARN, "vm-102", "never")
