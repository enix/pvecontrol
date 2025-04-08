from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from pvecontrol.utils import defaulter, dict_to_attr
from pvecontrol.models.vm import PVEVm, VmStatus


COLUMNS = ["node", "status", "allocatedcpu", "maxcpu", "mem", "allocatedmem", "maxmem"]


class NodeStatus(Enum):
    UNKNOWN = 0
    ONLINE = 1
    OFFLINE = 2


@dataclass
class PVENode:
    """A proxmox VE Node"""

    cluster: object
    node: str
    status: NodeStatus
    kwargs: Dict[str, Any] = field(default_factory=dict)

    cpu: int = field(init=True, default=0)
    allocatedcpu: int = field(init=True, default=0)
    maxcpu: int = field(init=True, default=0)
    mem: int = field(init=True, default=0)
    allocatedmem: int = field(init=True, default=0)
    maxmem: int = field(init=True, default=0)
    disk: int = field(init=True, default=0)
    maxdisk: int = field(init=True, default=0)
    vms: List[PVEVm] = field(default_factory=list)

    def __post_init__(self):
        dict_to_attr(self, "kwargs")
        self.status = NodeStatus[self.status.upper()]
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
