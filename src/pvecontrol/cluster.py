from proxmoxer import ProxmoxAPI

from node import PVENode

class PVECluster:
  """Proxmox VE Cluster"""


  def __init__(self, name, host, user, password, verify_ssl=False):
    self._api = ProxmoxAPI(host, user=user, password=password, verify_ssl=False)

    self.status = self._api.cluster.status.get()
    self.resources = self._api.cluster.resources.get()

    self.name =  name
    self.nodes = []
    for node in self._api.nodes.get():
      self.nodes.append(PVENode(self._api, node["node"], node["status"], node))

  def __str__(self):
    output = "Proxmox VE Cluster %s\n"%self.name
    output += "  Status: " + str(self.status) + "\n"
    output += "  Resources: " + str(self.resources) + "\n"
    output += "  Nodes:\n"
    for node in self.nodes:
      output += str(node) + "\n"
    return output

  def vms(self):
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
