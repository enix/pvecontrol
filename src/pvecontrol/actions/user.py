import click

from pvecontrol.cli import ResourceGroup
from pvecontrol.models.user import COLUMNS


@click.group(
    cls=ResourceGroup,
    name="user",
    columns=COLUMNS,
    default_sort="userid",
    list_callback=lambda proxmox: proxmox.users,
)
def root():
    pass
