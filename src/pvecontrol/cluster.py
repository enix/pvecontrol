import logging

from proxmoxer import ProxmoxAPI

from pvecontrol.node import PVENode
from pvecontrol.storage import PVEStorage
from pvecontrol.task import PVETask


class PVECluster:
  """Proxmox VE Cluster"""


  def __init__(self, name, host, user, password, config, verify_ssl=False):
    self._api = ProxmoxAPI(host, user=user, password=password, verify_ssl=verify_ssl)
    self.name =  name
    self.config = config
    self._initstatus()

  def _initstatus(self):
    self.status = self._api.cluster.status.get()
    self.resources = self._api.cluster.resources.get()

    self.nodes = []
    for node in self._api.nodes.get():
      self.nodes.append(PVENode(self._api, node["node"], node["status"], node))

    self.storages = []
    for storage in self.get_resources_storages():
      self.storages.append(PVEStorage(storage.pop("node"), storage.pop("id"), storage.pop("shared"), **storage))

    self.tasks = []
    for task in self._api.cluster.tasks.get():
      logging.debug("Get task informations: %s"%(str(task)))
      self.tasks.append(PVETask(self._api, task["upid"]))

  def refresh(self):
    self._initstatus()

  def __str__(self):
    output = "Proxmox VE Cluster %s\n"%self.name
    output += "  Status: " + str(self.status) + "\n"
    output += "  Resources: " + str(self.resources) + "\n"
    output += "  Nodes:\n"
    for node in self.nodes:
      output += str(node) + "\n"
    return output

  def vms(self):
    """Return all vms on this cluster"""
    vms = []
    for node in self.nodes:
      for vm in node.vms:
        vms.append(vm)
    return vms

  def find_node(self, nodename):
    """Check for node is running on this cluster"""
    for node in self.nodes:
      if node.node == nodename:
        return node
    return False

  def find_task(self, upid):
    """Return a task by upid"""
    for task in self.tasks:
      if task.upid == upid:
        return task
    return False

  def is_healthy(self):
    return bool([item for item in self.status if item.get('type') == 'cluster'][0]['quorate'])

  def get_resources_nodes(self):
    return [resource for resource in self.resources if resource["type"] == "node"]

  def get_resources_storages(self):
    return [resource for resource in self.resources if resource["type"] == "storage"]

  def cpu_metrics(self):
    nodes = self.get_resources_nodes()
    total_cpu = sum([node['maxcpu'] for node in nodes])
    total_cpu_usage = sum([node['cpu'] for node in nodes])
    total_cpu_allocated = sum([node.allocatedcpu for node in self.nodes])
    cpu_percent = total_cpu_usage / total_cpu *100

    return {
      "total": total_cpu,
      "usage": total_cpu_usage,
      "allocated": total_cpu_allocated,
      "percent": cpu_percent,
    }

  def memory_metrics(self):
    nodes = self.get_resources_nodes()
    total_memory = sum([node['maxmem'] for node in nodes])
    total_memory_usage = sum([node['mem'] for node in nodes])
    total_memory_allocated = sum([node.allocatedmem for node in self.nodes])
    memory_percent = total_memory_usage / total_memory *100

    return {
      "total": total_memory,
      "usage": total_memory_usage,
      "allocated": total_memory_allocated,
      "percent": memory_percent,
    }

  def disk_metrics(self):
    storages = self.get_resources_storages()
    total_disk = sum([node['maxdisk'] for node in storages])
    total_disk_usage = sum([node['disk'] for node in storages])
    disk_percent = total_disk_usage / total_disk *100

    return {
      "total": total_disk,
      "usage": total_disk_usage,
      "percent": disk_percent,
    }

  def metrics(self):
    return {
      "cpu": self.cpu_metrics(),
      "memory": self.memory_metrics(),
      "disk": self.disk_metrics()
    }
