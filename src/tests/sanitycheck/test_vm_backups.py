from unittest.mock import patch
from datetime import datetime, timedelta

import responses

from pvecontrol.sanitycheck.tests.vm_backups import VmBackups
from pvecontrol.sanitycheck import SanityCheck
from pvecontrol.sanitycheck.checks import CheckCode
from tests.testcase import PVEControlTestcase
from tests.fixtures.api import fake_backup


class PVEClusterTestcase(PVEControlTestcase):

    @responses.activate
    def test_check(self):
        self.responses_get("/api2/json/cluster/backup")
        data = [
            fake_backup("s3", 100, datetime.now() - timedelta(minutes=110)),
            fake_backup("s3", 101, datetime.now() - timedelta(minutes=90)),
        ]
        self.responses_get("/api2/json/nodes/pve-devel-1/storage/s3/content", data=data)

        vm_backups_check = VmBackups(self.cluster)
        vm_backups_check.run()

        def assert_message(message, expected_code, *message_contains):
            assert message.code == expected_code
            for string in message_contains:
                assert string in message.message

        sc = SanityCheck(self.cluster)
        with patch.object(sc, "_checks", new=[vm_backups_check]):
            exitcode = sc.get_exit_code()
            sc.display()

            assert exitcode == 1
            assert len(vm_backups_check.messages) == 8
            assert_message(vm_backups_check.messages[0], CheckCode.OK, "vm-100", "is associated")
            assert_message(vm_backups_check.messages[1], CheckCode.OK, "vm-101", "is associated")
            assert_message(vm_backups_check.messages[2], CheckCode.OK, "vm-102", "is associated")
            assert_message(vm_backups_check.messages[3], CheckCode.CRIT, "vm-103", "not associated")
            assert_message(vm_backups_check.messages[4], CheckCode.CRIT, "vm-104", "not associated")
            assert_message(vm_backups_check.messages[5], CheckCode.WARN, "vm-100", "more than")
            assert_message(vm_backups_check.messages[6], CheckCode.OK, "vm-101", "less than")
            assert_message(vm_backups_check.messages[7], CheckCode.WARN, "vm-102", "never")
