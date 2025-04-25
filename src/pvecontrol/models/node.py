from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional

from pvecontrol.utils import defaulter
from pvecontrol.models.vm import PVEVm, VmStatus


COLUMNS = ["node", "status", "allocatedcpu", "maxcpu", "mem", "allocatedmem", "maxmem"]


class NodeStatus(Enum):
    UNKNOWN = 0
    ONLINE = 1
    OFFLINE = 2


@dataclass
class PVENodeData:
    node: str = field(default="")
    status: Optional["NodeStatus"] = None
    cluster: Any = None
    cpu: int = field(default=0)
    allocatedcpu: int = field(default=0)
    maxcpu: int = field(default=0)
    mem: int = field(default=0)
    allocatedmem: int = field(default=0)
    maxmem: int = field(default=0)
    disk: int = field(default=0)
    maxdisk: int = field(default=0)
    vms: List = field(default_factory=list)


class PVENode(PVENodeData):
    """A proxmox VE Node"""

    def __init__(self, cluster, **kwargs):
        _values = {k: v for k, v in kwargs.items() if hasattr(PVENodeData, k)}
        super().__init__(**_values)
        if isinstance(self.status, str):
            self.status = NodeStatus[self.status.upper()]
        self.cluster = cluster
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
            self.vms = [PVEVm(self.api, **vm) for vm in self.resources_vms]

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
