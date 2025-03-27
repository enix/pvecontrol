import click

from pvecontrol.utils import print_task
from pvecontrol.cli import ResourceGroup, task_related_command
from pvecontrol.models.task import COLUMNS
from pvecontrol.models.cluster import PVECluster


@click.group(
    cls=ResourceGroup,
    name="task",
    columns=COLUMNS,
    default_sort="starttime",
    list_callback=lambda proxmox: proxmox.tasks,
)
def root():
    pass


@root.command()
@click.argument("upid")
@task_related_command
@click.pass_context
def get(ctx, upid, follow, wait):
    """Get detailled information about a task"""
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    print_task(proxmox, upid, follow, wait)
