import click

from pvecontrol.models.storage import PVEStorage, COLUMNS
from pvecontrol.models.cluster import PVECluster
from pvecontrol.utils import print_output
from pvecontrol.cli import with_table_options


@click.group()
def root():
    """Storage related commands"""


@root.command("list")
@with_table_options(COLUMNS, "storage")
@click.pass_context
def storage_list(ctx, sort_by, columns, filters):
    """Describe cluster storages"""
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    output = ctx.obj["args"].output
    storages = PVEStorage.get_grouped_list(proxmox)

    for item in storages:
        storage = item.pop("storage").__dict__
        storage.pop("node")
        item.update(storage)

    for storage in storages:
        storage["nodes"] = ", ".join(storage["nodes"])

    print_output(storages, columns=columns, sortby=sort_by, filters=filters, output=output)
