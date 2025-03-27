import click

from pvecontrol.models.storage import PVEStorage, COLUMNS
from pvecontrol.cli import ResourceGroup


@click.group(
    cls=ResourceGroup,
    name="storage",
    columns=COLUMNS,
    default_sort="storage",
    list_callback=PVEStorage.get_flattened_grouped_list,
)
def root():
    pass
