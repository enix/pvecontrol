import click

from pvecontrol.cli import ResourceGroup
from pvecontrol.models.acl import COLUMNS


@click.group(
    cls=ResourceGroup,
    name="acl",
    columns=COLUMNS,
    default_sort="path",
    list_callback=lambda proxmox: proxmox.acls,
)
def root():
    pass
