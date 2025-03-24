import logging
import sys

import click

from pvecontrol.utils import init_cluster, print_task, print_output, with_table_options, migration_related_command
from pvecontrol.models.vm import COLUMNS


@click.group()
def root():
    """VM related commands"""
    pass


@root.command("list")
@with_table_options(COLUMNS, "vmid")
@click.pass_context
def vm_list(ctx, sort_by, columns, filter):
    """List VMs in the Proxmox Cluster"""
    proxmox = init_cluster(ctx.obj["args"].cluster)
    output = ctx.obj["args"].output
    print_output(proxmox.vms, columns=columns, sortby=sort_by, filters=filter, output=output)


@root.command()
@click.argument("vmid")
@click.argument("target")
@migration_related_command
@click.pass_context
def migrate(ctx, vmid, target, online, follow, wait, dry_run):
    """Migrate VMs in the cluster"""

    proxmox = init_cluster(ctx.obj["args"].cluster)
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
        # pylint: disable=duplicate-code
        proxmox.refresh()
        _task = proxmox.find_task(upid)
        print_task(proxmox, upid, follow, wait)
    else:
        print("Dry run, skipping migration")


def _get_vm(proxmox, vmid):
    for v in proxmox.vms:
        logging.debug("_get_vm: %s", v)
        if v.vmid == vmid:
            return v
    return None
