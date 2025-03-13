import click

from pvecontrol.utils import print_task, print_output, with_table_options, task_related_command
from pvecontrol.models.task import COLUMNS
from pvecontrol.models.cluster import PVECluster


@click.group()
def root():
    """Task related commands"""


@root.command("list")
@with_table_options(COLUMNS, "starttime")
@click.pass_context
def task_list(ctx, sort_by, columns, filters):
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    output = ctx.obj["args"].output
    print_output(proxmox.tasks, columns=columns, sortby=sort_by, filters=filters, output=output)


@root.command()
@click.argument("upid")
@task_related_command
@click.pass_context
def get(ctx, upid, follow, wait):
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    print_task(proxmox, upid, follow, wait)
