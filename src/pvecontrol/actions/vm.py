import logging
import sys

import click

from pvecontrol.utils import print_task
from pvecontrol.cli import ResourceGroup, migration_related_command
from pvecontrol.models.vm import COLUMNS
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
