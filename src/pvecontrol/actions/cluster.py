import sys

import click

from humanize import naturalsize

from pvecontrol.models.node import NodeStatus
from pvecontrol.sanitycheck import SanityCheck
from pvecontrol.sanitycheck.tests import DEFAULT_CHECK_IDS
from pvecontrol.models.cluster import PVECluster
from pvecontrol.utils import OutputFormats, render_output


@click.command()
@click.pass_context
def status(ctx):
    """Show cluster status"""
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    cluster_status = "healthy" if proxmox.is_healthy else "not healthy"

    templates = sum(len(node.templates) for node in proxmox.nodes)
    vms = sum(len(node.vms) for node in proxmox.nodes)
    metrics = proxmox.metrics

    def _get_cpu_output():
        c_usage = metrics["cpu"]["usage"]
        c_total = metrics["cpu"]["total"]
        c_percent = metrics["cpu"]["percent"]
        c_allocated = metrics["cpu"]["allocated"]
        return f"{c_usage:.2f}/{c_total} ({c_percent:.1f}%), allocated: {c_allocated}"

    def _get_memory_output():
        m_usage = naturalsize(metrics["memory"]["usage"], binary=True, format="%.2f")
        m_total = naturalsize(metrics["memory"]["total"], binary=True, format="%.2f")
        m_percent = metrics["memory"]["percent"]
        m_allocated = naturalsize(metrics["memory"]["allocated"], binary=True, format="%.2f")
        return f"{m_usage}/{m_total}({m_percent:.1f}%), allocated: {m_allocated}"

    def _get_disk_output():
        d_usage = naturalsize(metrics["disk"]["usage"], binary=True, format="%.2f")
        d_total = naturalsize(metrics["disk"]["total"], binary=True, format="%.2f")
        d_percent = metrics["disk"]["percent"]
        return f"{d_usage}/{d_total}({d_percent:.1f}%)"

    if ctx.obj["args"].output == OutputFormats.TEXT:
        print(
            f"""\n\
  Status: {cluster_status}
  VMs: {vms - templates}
  Templates: {templates}
  Metrics:
    CPU: {_get_cpu_output()}
    Memory: {_get_memory_output()}
    Disk: {_get_disk_output()}
  Nodes:
    Offline: {len([node for node in proxmox.nodes if node.status == NodeStatus.OFFLINE])}
    Online: {len([node for node in proxmox.nodes if node.status == NodeStatus.ONLINE])}
    Unknown: {len([node for node in proxmox.nodes if node.status == NodeStatus.UNKNOWN])}
"""
        )
    else:
        render_table = [
            {
                "status": cluster_status,
                "vm": vms - templates,
                "templates": templates,
                "metrics": metrics,
                "nodes": {
                    "offline": len([node for node in proxmox.nodes if node.status == NodeStatus.OFFLINE]),
                    "online": len([node for node in proxmox.nodes if node.status == NodeStatus.ONLINE]),
                    "unknown": len([node for node in proxmox.nodes if node.status == NodeStatus.UNKNOWN]),
                },
            }
        ]
        print(render_output(render_table, output=ctx.obj["args"].output))


@click.command()
@click.argument("checks", nargs=-1, type=click.Choice(list(DEFAULT_CHECK_IDS), case_sensitive=False))
@click.pass_context
def sanitycheck(ctx, checks):
    """Check status of proxmox Cluster"""
    # More checks to implement
    # VM is started but 'startonboot' not set
    # VM is running in cpu = host
    # VM is running in cpu = qemu64
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    sc = SanityCheck(proxmox)
    exitcode = sc.run(checks=set(checks))
    sc.display()
    sys.exit(exitcode)
