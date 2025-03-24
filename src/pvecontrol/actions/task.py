import click

from pvecontrol.utils import init_cluster, print_task, print_output, with_table_options, task_related_command
from pvecontrol.models.task import COLUMNS


@click.group()
def root():
    """Task related commands"""
    pass


@root.command("list")
@with_table_options(COLUMNS, "starttime")
@click.pass_context
def task_list(ctx, sort_by, columns, filter):
    proxmox = init_cluster(ctx.obj["args"].cluster)
    output = ctx.obj["args"].output
    print_output(proxmox.tasks, columns=columns, sortby=sort_by, filters=filter, output=output)


@root.command()
@click.argument("upid")
@task_related_command
@click.pass_context
def get(ctx, upid, follow, wait):
    proxmox = init_cluster(ctx.obj["args"].cluster)
    print_task(proxmox, upid, follow, wait)
