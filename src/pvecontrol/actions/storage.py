import click

from pvecontrol.models.storage import PVEStorage, COLUMNS
from pvecontrol.utils import print_output, add_table_options


@click.group()
def root():
    """Storage related commands"""
    pass


@root.command("list")
@add_table_options(COLUMNS, "storage")
@click.pass_context
def storage_list(ctx, sort_by, columns, filter):
    """Describe cluster storages"""
    proxmox = ctx.obj["cluster"]
    output = ctx.obj["args"].output
    storages = PVEStorage.get_grouped_list(proxmox)

    for item in storages:
        storage = item.pop("storage").__dict__
        storage.pop("node")
        item.update(storage)

    for storage in storages:
        storage["nodes"] = ", ".join(storage["nodes"])

    print_output(storages, columns=columns, sortby=sort_by, filters=filter, output=output)
