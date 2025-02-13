from unittest.mock import patch
from datetime import datetime, timedelta
from pvecontrol.cluster import PVECluster
from pvecontrol.sanitycheck.tests.vm_backups import VmBackups
from pvecontrol.sanitycheck import SanityCheck
from pvecontrol.sanitycheck.checks import CheckCode
from tests.fixtures.api import mock_api_requests, fake_node, fake_vm, fake_backup_job, fake_backup


@patch("proxmoxer.backends.https.ProxmoxHTTPAuth")
@patch("proxmoxer.backends.https.ProxmoxHttpSession.request")
def test_sanitycheck_vm_backups(request, _proxmox_http_auth):
    nodes = [
        fake_node(3, True),
        fake_node(4, True),
    ]
    vms = [
        fake_vm(100, nodes[0]),
        fake_vm(101, nodes[0]),
        fake_vm(102, nodes[1]),
        fake_vm(103, nodes[1]),
    ]
    backup_jobs = [
        fake_backup_job(1, "100"),
        fake_backup_job(2, "101"),
        fake_backup_job(3, "102"),
    ]
    storages_contents = [
        fake_backup("s3", 100, datetime.now() - timedelta(minutes=110)),
        fake_backup("s3", 101, datetime.now() - timedelta(minutes=90)),
    ]

    request.side_effect = mock_api_requests(nodes, vms, backup_jobs, storages_contents)

    proxmox = PVECluster(
        "name",
        "host",
        config={
            "node": {
                "cpufactor": 2.5,
                "memoryminimum": 81928589934592,
            },
            "vm": {
                "max_last_backup": 100,
            },
        },
        **{"user": "user", "password": "password"},
        timeout=1,
    )

    vm_backups_check = VmBackups(proxmox)
    vm_backups_check.run()

    def assert_message(message, expected_code, *message_contains):
        assert message.code == expected_code
        for string in message_contains:
            assert string in message.message

    sc = SanityCheck(proxmox)
    with patch.object(sc, "_checks", new=[vm_backups_check]):
        exitcode = sc.get_exit_code()
        sc.display()

        assert exitcode == 1
        assert len(vm_backups_check.messages) == 7
        assert_message(vm_backups_check.messages[0], CheckCode.OK, "vm-100", "is associated")
        assert_message(vm_backups_check.messages[1], CheckCode.OK, "vm-101", "is associated")
        assert_message(vm_backups_check.messages[2], CheckCode.OK, "vm-102", "is associated")
        assert_message(vm_backups_check.messages[3], CheckCode.WARN, "vm-103", "not associated")
        assert_message(vm_backups_check.messages[4], CheckCode.CRIT, "vm-100", "(vm-100) last backup")
        assert_message(vm_backups_check.messages[5], CheckCode.OK, "vm-101", "not been backed up in the last")
        assert_message(vm_backups_check.messages[6], CheckCode.WARN, "vm-102", "never")
