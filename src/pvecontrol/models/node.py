from enum import Enum

from pvecontrol.utils import defaulter
from pvecontrol.models.vm import PVEVm, VmStatus


COLUMNS = ["node", "status", "allocatedcpu", "maxcpu", "mem", "allocatedmem", "maxmem"]


class NodeStatus(Enum):
    UNKNOWN = 0
    ONLINE = 1
    OFFLINE = 2


class PVENode:
    """A proxmox VE Node"""

    def __init__(self, cluster, node, status, kwargs=None):
        if not kwargs:
            kwargs = {}

        self.node = node
        self.status = NodeStatus[status.upper()]
        self.cluster = cluster
        self.cpu = kwargs.get("cpu", 0)
        self.allocatedcpu = 0
        self.maxcpu = kwargs.get("maxcpu", 0)
        self.mem = kwargs.get("mem", 0)
        self.allocatedmem = 0
        self.maxmem = kwargs.get("maxmem", 0)
        self.disk = kwargs.get("disk", 0)
        self.maxdisk = kwargs.get("maxdisk", 0)
        self._init_vms()
        self._init_allocatedmem()
        self._init_allocatedcpu()

    def __str__(self):
        output = "Node: " + self.node + "\n"
        output += "Status: " + str(self.status) + "\n"
        output += f"CPU: {self.cpu}/{self.allocatedcpu}/{self.maxcpu}\n"
        output += f"Mem: {self.mem}/{self.allocatedmem}/{self.maxmem}\n"
        output += f"Disk: {self.disk}/{self.maxdisk}\n"
        output += "VMs: \n"
        for vm in self.vms:
            output += f" - {vm}\n"
        return output

    def _init_vms(self):
        self.vms = []
        if self.status == NodeStatus.ONLINE:
            self.vms = [PVEVm(self.api, self.node, vm["vmid"], vm["status"], vm) for vm in self.resources_vms]

    def _init_allocatedmem(self):
        """Compute the amount of memory allocated to running VMs"""
        self.allocatedmem = 0
        for vm in self.vms:
            if vm.status != VmStatus.RUNNING:
                continue
            self.allocatedmem += vm.maxmem

    def _init_allocatedcpu(self):
        """Compute the amount of cpu allocated to running VMs"""
        self.allocatedcpu = 0
        for vm in self.vms:
            if vm.status != VmStatus.RUNNING:
                continue
            self.allocatedcpu += vm.cpus

    @property
    def api(self):
        return self.cluster.api

    @property
    def resources(self):
        return [resource for resource in self.cluster.resources if resource.get("node") == self.node]

    @property
    def resources_vms(self):
        return [
            defaulter(resource, ["maxcpu", "maxdisk", "maxmem"], 0)
            for resource in self.resources
            if resource["type"] == "qemu"
        ]

    # def __contains__(self, item):
    #   """Check if a VM is running on this node"""
    #   for vm in self.vms:
    #     if vm.vmid == item:
    #       return True
    #   return False

    @property
    def templates(self):
        return [vm for vm in self.vms if vm.template]
