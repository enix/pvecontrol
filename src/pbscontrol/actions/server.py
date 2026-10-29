import click

from humanize import naturalsize

from pbscontrol.models.server import PBSServer
from pvecontrol.utils import OutputFormats, render_output


@click.command()
@click.pass_context
def status(ctx):
    """Show Proxmox Backup Server status"""
    pbs = PBSServer.create_from_config(ctx.obj["args"].server)
    usage = pbs.datastore_usage

    if ctx.obj["args"].output == OutputFormats.TEXT:
        print(f"""\n\
  Name: {pbs.name}
  Version: {pbs.version.get('version', 'unknown')}
  Datastores:""")
        for ds in usage:
            total = naturalsize(ds["total"], binary=True, format="%.2f")
            used = naturalsize(ds["used"], binary=True, format="%.2f")
            avail = naturalsize(ds["avail"], binary=True, format="%.2f")
            percent = ds["used"] / ds["total"] * 100 if ds["total"] else 0
            print(f"    {ds['store']}: {used}/{total} ({percent:.1f}%), available: {avail}, gc: {ds['gc-status']}")
        print()
    else:
        render_table = [
            {
                "store": ds["store"],
                "total": ds["total"],
                "used": ds["used"],
                "avail": ds["avail"],
                "percent": round(ds["used"] / ds["total"] * 100 if ds["total"] else 0, 1),
                "gc-status": ds["gc-status"],
            }
            for ds in usage
        ]
        print(render_output(render_table, output=ctx.obj["args"].output))
