import click

from pvecontrol.cli import ResourceGroup
from pvecontrol.models.group import COLUMNS


@click.group(
    cls=ResourceGroup,
    name="group",
    columns=COLUMNS,
    default_sort="groupid",
    list_callback=lambda proxmox: proxmox.groups,
)
def root():
    pass
