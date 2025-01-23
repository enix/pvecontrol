import sys

from humanize import naturalsize

from pvecontrol.node import NodeStatus
from pvecontrol.sanitycheck import SanityCheck


def action_clusterstatus(proxmox, _args):
    status = "healthy" if proxmox.is_healthy else "not healthy"

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

    output = f"""
  Status: {status}
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

    print(output)


def action_sanitycheck(proxmox, args):
    """Check status of proxmox Cluster"""
    # More checks to implement
    # VM is started but 'startonboot' not set
    # VM is running in cpu = host
    # VM is running in cpu = qemu64
    sc = SanityCheck(proxmox)
    exitcode = sc.run(checks=args.check)
    sc.display()
    sys.exit(exitcode)
