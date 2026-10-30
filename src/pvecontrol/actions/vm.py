import logging
import sys

import click
import proxmoxer.core

from pvecontrol.utils import confirm, exit_if_task_failed, print_task
from pvecontrol.cli import ResourceGroup, migration_related_command, task_related_command
from pvecontrol.models.vm import PVEVm, VmStatus, COLUMNS
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
    vmid = int(vmid)
    target = str(target)

    vm = proxmox.get_vm(vmid)
    logging.debug("Source vm: %s", vm)
    if not vm:
        logging.error("Source VM %s not found", vmid)
        sys.exit(1)
    _exit_if_node_offline(proxmox, vm)
    node = proxmox.find_node(vm.node)
    if not node:
        logging.error("Source node %s does not exist", vm.node)
        sys.exit(1)
    logging.debug("Source node: %s", node)

    target_node = proxmox.find_node(target)
    if not target_node:
        logging.error("Target node %s does not exist", target)
        sys.exit(1)
    if not target_node.online:
        logging.error("Target node %s is not online", target_node.node)
        sys.exit(1)

    try:
        upid = vm.migrate(target_node.node, online, dry_run=dry_run)
    except proxmoxer.core.ResourceException as e:
        logging.error("Error migrating VM %s: %s", vmid, e)
        sys.exit(1)
    if dry_run:
        print("Dry run, skipping migration")
        return
    _follow_task(proxmox, upid, follow, wait)


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

    if not proxmox.is_node_online(target):
        logging.error("Target node %s does not exist or is not online", target)
        sys.exit(1)

    try:
        upid = PVEVm.create(proxmox, vmid, target, archive=archive, storage=storage, force=force)
    except proxmoxer.core.ResourceException as e:
        logging.error("Error creating VM: %s", e)
        sys.exit(1)
    _follow_task(proxmox, upid, follow, wait)


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

    vm = proxmox.get_vm(vmid)
    logging.debug("Vm to unlock: %s", vm)
    if not vm:
        logging.error("VM %s to unlock not found", vmid)
        sys.exit(1)
    _exit_if_node_offline(proxmox, vm)

    if not vm.lock:
        print(f"VM {vm.vmid} ({vm.name}) is not locked")
        return

    print(f"Removing lock '{vm.lock}' on VM {vm.vmid} ({vm.name})")
    if not confirm(force):
        sys.exit(1)

    if dry_run:
        print("Dry run, skipping unlock")
        return

    try:
        vm.unlock()
    except proxmoxer.core.ResourceException as e:
        logging.error("Error unlocking VM, note that removing a lock requires root@pam: %s", e)
        sys.exit(1)

    print(f"Lock '{vm.lock}' removed from VM {vm.vmid} ({vm.name})")


@root.command()
@click.argument("vmid", type=int)
@click.option("--dry-run", is_flag=True, help="Dry run, do not start the VM for real")
@click.option("--force", is_flag=True, help="Do not ask for confirmation before starting the VM")
@task_related_command
@click.pass_context
def start(ctx, vmid, dry_run, force, follow, wait):
    """Start a VM"""

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    vmid = int(vmid)

    vm = proxmox.get_vm(vmid)
    if not vm:
        logging.error("VM %s not found", vmid)
        sys.exit(1)
    _exit_if_node_offline(proxmox, vm)

    if vm.status == VmStatus.RUNNING:
        logging.warning("VM %s is already running", vmid)
        return

    print(f"Starting VM {vm.vmid} ({vm.name})")
    if dry_run:
        print("Dry run, skipping start")
        return

    if not confirm(force):
        sys.exit(1)

    try:
        upid = vm.start()
    except proxmoxer.core.ResourceException as e:
        logging.error("Error starting VM %s: %s", vmid, e)
        sys.exit(1)
    _follow_task(proxmox, upid, follow, wait)


@root.command()
@click.argument("vmid", type=int)
@click.option(
    "--timeout",
    type=int,
    metavar="SECONDS",
    help="Wait at most SECONDS for the shutdown to complete",
)
@click.option("--dry-run", is_flag=True, help="Dry run, do not shutdown the VM for real")
@click.option("--force", is_flag=True, help="Do not ask for confirmation before shutting down the VM")
@task_related_command
@click.pass_context
def shutdown(ctx, vmid, timeout, dry_run, force, follow, wait):
    """Cleanly shutdown a VM"""

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    vmid = int(vmid)

    vm = proxmox.get_vm(vmid)
    if not vm:
        logging.error("VM %s not found", vmid)
        sys.exit(1)
    _exit_if_node_offline(proxmox, vm)

    if vm.status == VmStatus.STOPPED:
        logging.warning("VM %s is already stopped", vmid)
        return

    print(f"Shutting down VM {vm.vmid} ({vm.name})")
    if dry_run:
        print("Dry run, skipping shutdown")
        return

    if not confirm(force):
        sys.exit(1)

    try:
        upid = vm.shutdown(timeout=timeout)
    except proxmoxer.core.ResourceException as e:
        logging.error("Error shutting down VM %s: %s", vmid, e)
        sys.exit(1)
    _follow_task(proxmox, upid, follow, wait)


@root.command()
@click.argument("vmid", type=int)
@click.option("--overrule-shutdown", is_flag=True, help="Override any in-progress shutdown task")
@click.option("--dry-run", is_flag=True, help="Dry run, do not stop the VM for real")
@click.option("--force", is_flag=True, help="Do not ask for confirmation before stopping the VM")
@task_related_command
@click.pass_context
def stop(ctx, vmid, overrule_shutdown, dry_run, force, follow, wait):
    """Stop a VM"""

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    vmid = int(vmid)

    vm = proxmox.get_vm(vmid)
    if not vm:
        logging.error("VM %s not found", vmid)
        sys.exit(1)
    _exit_if_node_offline(proxmox, vm)

    if vm.status == VmStatus.STOPPED:
        logging.warning("VM %s is already stopped", vmid)
        return

    print(f"Stopping VM {vm.vmid} ({vm.name})")
    if dry_run:
        print("Dry run, skipping stop")
        return

    if not confirm(force):
        sys.exit(1)

    try:
        upid = vm.stop(overrule_shutdown=overrule_shutdown)
    except proxmoxer.core.ResourceException as e:
        logging.error("Error stopping VM %s: %s", vmid, e)
        sys.exit(1)
    _follow_task(proxmox, upid, follow, wait)


def _exit_if_node_offline(proxmox, vm):
    if not proxmox.is_node_online(vm.node):
        logging.error("VM %s (%s) is on node %s, which is not online", vm.vmid, vm.name, vm.node)
        sys.exit(1)


def _follow_task(proxmox, upid, follow, wait):
    """Display the task started by a command, exit in error if it was followed or waited for and failed"""
    proxmox.refresh()
    task = print_task(proxmox, upid, follow, wait)
    exit_if_task_failed(task, follow, wait)
