import logging
import fnmatch

from proxmoxer import ProxmoxAPI

from pvecontrol.node import PVENode
from pvecontrol.storage import PVEStorage
from pvecontrol.task import PVETask


class PVECluster:
    """Proxmox VE Cluster"""

    def __init__(self, name, host, config, verify_ssl=False, **auth):
        self.api = ProxmoxAPI(host, verify_ssl=verify_ssl, **auth)
        self.name = name
        self.config = config
        self._initstatus()

    def _initstatus(self):
        self.status = self.api.cluster.status.get()
        self.resources = self.api.cluster.resources.get()

        self.nodes = []
        for node in self.api.nodes.get():
            self.nodes.append(PVENode(self.api, node["node"], node["status"], node))

        self.storages = []
        for storage in self.get_resources_storages():
            self.storages.append(PVEStorage(storage.pop("node"), storage.pop("id"), storage.pop("shared"), **storage))

        self.ha = {
            "groups": self.api.cluster.ha.groups.get(),
            "manager_status": self.api.cluster.ha.status.manager_status.get(),
            "resources": self.api.cluster.ha.resources.get(),
        }

        self.tasks = []
        for task in self.api.cluster.tasks.get():
            logging.debug("Get task informations: %s", (str(task)))
            self.tasks.append(PVETask(self.api, task["upid"]))

    def refresh(self):
        self._initstatus()

    def __str__(self):
        output = f"Proxmox VE Cluster {self.name}\n"
        output += f"  Status: {self.status}\n"
        output += f"  Resources: {self.resources}\n"
        output += "  Nodes:\n"
        for node in self.nodes:
            output += f"{node}\n"
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

    def find_nodes(self, pattern):
        """Find a list of nodes running on this cluster based on a glob pattern"""
        nodes = []
        for node in self.nodes:
            if fnmatch.fnmatchcase(node.node, pattern):
                nodes.append(node)
        return nodes

    def find_task(self, upid):
        """Return a task by upid"""
        for task in self.tasks:
            if task.upid == upid:
                return task
        return False

    def is_healthy(self):
        return bool([item for item in self.status if item.get("type") == "cluster"][0]["quorate"])

    def get_resources_nodes(self):
        return [resource for resource in self.resources if resource["type"] == "node"]

    def get_vm(self, vm_id):
        if isinstance(vm_id, str):
            vm_id = int(vm_id)

        result = None
        node_name = None
        for vm in self.get_resources_vms():
            if vm["vmid"] == vm_id:
                node_name = vm["node"]
                break

        for node in self.nodes:
            if node.node == node_name:
                result = [v for v in node.vms if v.vmid == vm_id][0]
                break

        return result

    def get_resources_vms(self):
        return [resource for resource in self.resources if resource["type"] == "qemu"]

    def get_resources_storages(self):
        return [resource for resource in self.resources if resource["type"] == "storage"]

    def get_storage(self, storage_name):
        return next(filter(lambda s: s.storage == storage_name, self.storages), None)

    def cpu_metrics(self):
        nodes = self.get_resources_nodes()
        total_cpu = sum(node["maxcpu"] for node in nodes)
        total_cpu_usage = sum(node["cpu"] for node in nodes)
        total_cpu_allocated = sum(node.allocatedcpu for node in self.nodes)
        cpu_percent = total_cpu_usage / total_cpu * 100

        return {
            "total": total_cpu,
            "usage": total_cpu_usage,
            "allocated": total_cpu_allocated,
            "percent": cpu_percent,
        }

    def memory_metrics(self):
        nodes = self.get_resources_nodes()
        total_memory = sum(node["maxmem"] for node in nodes)
        total_memory_usage = sum(node["mem"] for node in nodes)
        total_memory_allocated = sum(node.allocatedmem for node in self.nodes)
        memory_percent = total_memory_usage / total_memory * 100

        return {
            "total": total_memory,
            "usage": total_memory_usage,
            "allocated": total_memory_allocated,
            "percent": memory_percent,
        }

    def disk_metrics(self):
        storages = self.get_resources_storages()
        total_disk = sum(node["maxdisk"] for node in storages)
        total_disk_usage = sum(node["disk"] for node in storages)
        disk_percent = total_disk_usage / total_disk * 100

        return {
            "total": total_disk,
            "usage": total_disk_usage,
            "percent": disk_percent,
        }

    def metrics(self):
        return {
            "cpu": self.cpu_metrics(),
            "memory": self.memory_metrics(),
            "disk": self.disk_metrics(),
        }
