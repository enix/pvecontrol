import click

from pvecontrol.utils import print_task, print_output, add_table_options, task_related_command
from pvecontrol.models.task import COLUMNS


@click.group()
def root():
    pass


@root.command("list")
@add_table_options(COLUMNS, "starttime")
@click.pass_context
def task_list(ctx, sort_by, columns, filter):
    proxmox = ctx.obj["cluster"]
    output = ctx.obj["args"].output
    print_output(proxmox.tasks, columns=columns, sortby=sort_by, filters=filter, output=output)


@root.command()
@click.argument("upid")
@task_related_command
@click.pass_context
def get(ctx, upid, follow, wait):
    proxmox = ctx.obj["cluster"]
    print_task(proxmox, upid, follow, wait)
