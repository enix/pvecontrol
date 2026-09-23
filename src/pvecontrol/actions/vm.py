import logging
import sys

import click
import proxmoxer.core

from pvecontrol.utils import confirm, print_task
from pvecontrol.cli import ResourceGroup, migration_related_command, task_related_command
from pvecontrol.models.vm import PVEVm, COLUMNS
from pvecontrol.models.cluster import PVECluster


@click.group(
    cls=ResourceGroup,
    name="VM",
    columns=COLUMNS,
    default_sort="vmid",
    list_callback=lambda proxmox: proxmox.vms,
)
def root():
    pass


@root.command()
@click.argument("vmid", type=int)
@click.option(
    "-t",
    "--target",
    metavar="NODEID",
    required=True,
    help="ID of the target node",
)
@migration_related_command
@click.pass_context
def migrate(ctx, vmid, target, online, follow, wait, dry_run):
    """Migrate VMs in the cluster"""

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    logging.debug("ARGS: %s", ctx.obj["args"])
    # Migrate a vm to a node
    vmid = int(vmid)
    target = str(target)

    # Check that vmid exists
    vm = _get_vm(proxmox, vmid)
    logging.debug("Source vm: %s", vm)
    if not vm:
        print("Source vm not found")
        sys.exit(1)
    # Get source node
    node = proxmox.find_node(vm.node)
    if not node:
        print("Source node does not exists")
        sys.exit(1)
    logging.debug("Source node: %s", node)

    # Check target node exists
    target = proxmox.find_node(target)
    if not target:
        print("Target node does not exists")
        sys.exit(1)
    # Check target node a les ressources
    # FIXME

    # Check que la migration est possible
    check = proxmox.api.nodes(node.node).qemu(vmid).migrate.get(node=node.node, target=target.node)
    logging.debug("Migration check: %s", check)
    options = {}
    options["node"] = node.node
    options["target"] = target.node
    options["online"] = int(online)
    if len(check["local_disks"]) > 0:
        options["with-local-disks"] = int(True)

    if not dry_run:
        # Lancer tache de migration
        upid = proxmox.api.nodes(node.node).qemu(vmid).migrate.post(**options)
        # Suivre la task cree
        proxmox.refresh()
        print_task(proxmox, upid, follow, wait)
    else:
        print("Dry run, skipping migration")


@root.command()
@click.argument("vmid", type=int)
@click.option("-t", "--target", metavar="NODEID", required=True, help="ID of the target node")
@click.option(
    "-a",
    "--archive",
    metavar="ARCHIVE",
    required=True,
    help="The archive to restore. Either the file system path to a .tar or .vma file or a proxmox storage backup volume identifier.",
)
@click.option(
    "-s",
    "--storage",
    metavar="STORAGE",
    help="Target storage ID where the VM's disks will be created (defaults to the storage from the backup configuration).",
)
@click.option("--force", is_flag=True, help="Overwrite existing VM")
@task_related_command
@click.pass_context
def restore(ctx, vmid, target, archive, storage, force, follow, wait):
    """Restore a VM from a backup archive"""

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)

    try:
        upid = PVEVm.create(proxmox, vmid, target, archive=archive, storage=storage, force=force)
        proxmox.refresh()
        print_task(proxmox, upid, follow, wait)
    except proxmoxer.core.ResourceException as e:
        logging.error("Error creating VM: %s", e)
        sys.exit(1)


@root.command()
@click.argument("vmid", type=int)
@click.option("--dry-run", is_flag=True, help="Dry run, do not remove the lock for real")
@click.option("--force", is_flag=True, help="Do not ask for confirmation before removing the lock")
@click.pass_context
def unlock(ctx, vmid, dry_run, force):
    """Remove the lock set on a VM

    This requires the cluster to be authenticated as root@pam: unlocking relies on the skiplock option of
    the Proxmox API, which is restricted to root@pam by a hardcoded check in the API source, at least up to
    PVE 9.2. No role or permission can grant it to another user.
    """

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)

    vm = _get_vm(proxmox, vmid)
    logging.debug("Vm to unlock: %s", vm)
    if not vm:
        print("Vm to unlock not found")
        sys.exit(1)

    if not vm.lock:
        print(f"VM {vm.vmid} ({vm.name}) is not locked")
        return

    print(f"Removing lock '{vm.lock}' on VM {vm.vmid} ({vm.name})")
    if not confirm(force):
        return

    if dry_run:
        print("Dry run, skipping unlock")
        return

    try:
        vm.unlock()
    except proxmoxer.core.ResourceException as e:
        logging.error("Error unlocking VM, note that removing a lock requires root@pam: %s", e)
        sys.exit(1)

    print(f"Lock '{vm.lock}' removed from VM {vm.vmid} ({vm.name})")


# FIXME: merge with PVECluster.get_vm()
def _get_vm(proxmox, vmid):
    for v in proxmox.vms:
        logging.debug("_get_vm: %s", v)
        if v.vmid == vmid:
            return v
    return None
