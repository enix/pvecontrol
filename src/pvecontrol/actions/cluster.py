from humanize import naturalsize

from pvecontrol.node import NodeStatus
from pvecontrol.sanitycheck import SanityCheck


def action_clusterstatus(proxmox, args):
  status = "healthy" if proxmox.is_healthy() else "not healthy"

  templates = sum([len(node.templates()) for node in proxmox.nodes])
  vms = sum([len(node.vms) for node in proxmox.nodes])
  metrics = proxmox.metrics()

  metrics_cpu_output = "{:.2f}/{}({:.1f}%), allocated: {}".format(
    metrics['cpu']['usage'],
    metrics['cpu']['total'],
    metrics['cpu']['percent'],
    metrics['cpu']['allocated']
  )

  metrics_memory_output = "{}/{}({:.1f}%), allocated: {}".format(
    naturalsize(metrics['memory']['usage'], binary=True, format="%.2f"),
    naturalsize(metrics['memory']['total'], binary=True, format="%.2f"),
    metrics['memory']['percent'],
    naturalsize(metrics['memory']['allocated'], binary=True, format="%.2f"),
  )

  metrics_disk_output = "{}/{}({:.1f}%)".format(
    naturalsize(metrics['disk']['usage'], binary=True, format="%.2f"),
    naturalsize(metrics['disk']['total'], binary=True, format="%.2f"),
    metrics['disk']['percent']
  )

  output = f"""
  Status: {status}
  VMs: {vms - templates}
  Templates: {templates}
  Metrics:
    CPU: {metrics_cpu_output}
    Memory: {metrics_memory_output}
    Disk: {metrics_disk_output}
  Nodes:
    Offline: {len([node for node in proxmox.nodes if node.status == NodeStatus.offline])}
    Online: {len([node for node in proxmox.nodes if node.status == NodeStatus.online])}
    Unknown: {len([node for node in proxmox.nodes if node.status == NodeStatus.unknown])}
  """

  print(output)

def action_sanitycheck(proxmox, args):
  """Check status of proxmox Cluster"""
  # More checks to implement
  # VM is started but 'startonboot' not set
  # VM is running in cpu = host
  # VM is running in cpu = qemu64
  sc = SanityCheck(proxmox)
  sc.run()
  sc.display()
