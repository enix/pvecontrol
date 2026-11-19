import logging
import sys

import click
import proxmoxer.core

from pvecontrol.models.cluster import PVECluster
from pvecontrol.models.crs import CRS_MODES, CRS_REBALANCE_METHODS, PVECrs
from pvecontrol.utils import confirm, print_output

# Options of the set command that only matter when auto-rebalance is enabled
AUTO_REBALANCE_SETTINGS = ["threshold", "hold_duration", "margin", "method"]


@click.group(name="crs", help="HA Cluster Resource Scheduler (CRS) related commands")
def root():
    pass


def _read_crs(proxmox):
    try:
        return proxmox.crs
    except proxmoxer.core.ResourceException as e:
        logging.error("Cannot read the CRS settings, note that it requires Sys.Audit on /: %s", e)
    except ValueError as e:
        logging.error("Cannot parse the CRS settings: %s", e)
    sys.exit(1)


def _describe(crs):
    return crs.to_property_string() or "(all defaults)"


@root.command()
@click.pass_context
def show(ctx):
    """Show the HA Cluster Resource Scheduler settings

    Options that are not configured take their Proxmox VE default. The current imbalance of the cluster, as
    computed by the HA manager, is shown when Proxmox VE provides it (9.2 and later).
    """
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    crs = _read_crs(proxmox)
    rows = crs.to_rows()

    try:
        imbalance = proxmox.ha_imbalance
    except proxmoxer.core.ResourceException as e:
        logging.warning("Cannot read the HA manager status: %s", e)
        imbalance = None
    if imbalance is not None:
        rows.append({"option": "imbalance", "value": f"{imbalance * 100:.1f}%", "source": "ha manager"})

    print_output(rows, output=ctx.obj["args"].output)


@root.command(name="set")
@click.option("--mode", type=click.Choice(CRS_MODES), help="Scheduling mode (ha)")
@click.option(
    "--rebalance-on-start/--no-rebalance-on-start",
    default=None,
    help="Select a suited node when an HA resource is started (ha-rebalance-on-start)",
)
@click.option(
    "--auto-rebalance/--no-auto-rebalance",
    default=None,
    help="Automatically rebalance HA resources, static and dynamic modes only (ha-auto-rebalance)",
)
@click.option(
    "--threshold",
    type=click.FloatRange(0, 100),
    metavar="PERCENT",
    help="Imbalance above which auto-rebalance triggers (ha-auto-rebalance-threshold)",
)
@click.option(
    "--hold-duration",
    type=click.FloatRange(min=0),
    metavar="ROUNDS",
    help="HA rounds (about 10 s each) the threshold must be exceeded for (ha-auto-rebalance-hold-duration)",
)
@click.option(
    "--margin",
    type=click.FloatRange(0, 100),
    metavar="PERCENT",
    help="Minimum imbalance improvement for a migration (ha-auto-rebalance-margin)",
)
@click.option(
    "--method",
    type=click.Choice(CRS_REBALANCE_METHODS),
    help="Rebalancing method (ha-auto-rebalance-method)",
)
@click.option("--reset", is_flag=True, help="Remove all the CRS settings, back to the Proxmox VE defaults")
@click.option("--dry-run", is_flag=True, help="Show the resulting settings, do not write them")
@click.option("--force", is_flag=True, help="Do not ask for confirmation before writing the settings")
@click.pass_context
def set_crs(ctx, reset, dry_run, force, **changes):
    """Change the HA Cluster Resource Scheduler settings

    Options left out keep their current value. Proxmox VE stores the settings in a single value of the
    datacenter configuration: they are read, changed and written back as a whole.
    """
    changed = {attribute: value for attribute, value in changes.items() if value is not None}
    if reset and changed:
        raise click.UsageError("--reset can't be combined with other settings")
    if not reset and not changed:
        raise click.UsageError("Nothing to change, give at least one setting or --reset")

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    current = _read_crs(proxmox)
    new = PVECrs() if reset else current.update(**changed)

    errors = new.validate()
    if errors:
        for error in errors:
            logging.error("Invalid CRS settings: %s", error)
        sys.exit(1)
    if not new.auto_rebalance and any(attribute in changed for attribute in AUTO_REBALANCE_SETTINGS):
        logging.warning("Auto-rebalance is disabled, its settings have no effect until it is enabled")

    print(f"Current CRS settings: {_describe(current)}")
    print(f"New CRS settings: {_describe(new)}")
    if new == current:
        print("CRS settings unchanged")
        return

    if dry_run:
        print("Dry run, skipping update")
        return
    if not confirm(force):
        sys.exit(1)

    try:
        if reset:
            proxmox.reset_crs()
        else:
            proxmox.set_crs(new)
    except proxmoxer.core.ResourceException as e:
        logging.error("Error writing the CRS settings, note that it requires Sys.Modify on /: %s", e)
        sys.exit(1)

    print("CRS settings updated")
