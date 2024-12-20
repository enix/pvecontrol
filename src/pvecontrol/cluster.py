import logging
import fnmatch

from proxmoxer import ProxmoxAPI

from pvecontrol.node import PVENode
from pvecontrol.storage import PVEStorage
from pvecontrol.task import PVETask
from pvecontrol.backup_job import PVEBackupJob
from pvecontrol.volume import PVEVolume


class PVECluster:
    """Proxmox VE Cluster"""

    def __init__(self, name, host, config, timeout, verify_ssl=False, **auth):
        self.api = ProxmoxAPI(host, timeout=timeout, verify_ssl=verify_ssl, **auth)
        self.name = name
        self.config = config
        self._tasks = None
        self._ha = None
        self._backups = None
        self._backup_jobs = None
        self._initstatus()

    def _initstatus(self):
        self.status = self.api.cluster.status.get()
        self.resources = self.api.cluster.resources.get()

        self.nodes = []
        for node in self.resources_nodes:
            self.nodes.append(
                PVENode(
                    self,
                    node["node"],
                    node["status"],
                    kwargs=node,
                )
            )

        self.storages = []
        for storage in self.resources_storages:
            self.storages.append(
                PVEStorage(self.api, storage.pop("node"), storage.pop("id"), storage.pop("shared"), **storage)
            )

    @property
    def ha(self):
        if self._ha is not None:
            return self._ha

        self._ha = {
            "groups": self.api.cluster.ha.groups.get(),
            "manager_status": self.api.cluster.ha.status.manager_status.get(),
            "resources": self.api.cluster.ha.resources.get(),
        }
        return self._ha

    @property
    def tasks(self):
        if self._tasks is not None:
            return self._tasks

        self._tasks = []
        for task in self.api.cluster.tasks.get():
            logging.debug("Get task informations: %s", (str(task)))
            self._tasks.append(PVETask(self.api, task["upid"]))
        return self._tasks

    def refresh(self):
        self._initstatus()

        # force tasks refesh
        self._tasks = None
        _ = self.tasks

        # force ha information refesh
        self._ha = None
        _ = self.ha

    def __str__(self):
        output = f"Proxmox VE Cluster {self.name}\n"
        output += f"  Status: {self.status}\n"
        output += f"  Resources: {self.resources}\n"
        output += "  Nodes:\n"
        for node in self.nodes:
            output += f"{node}\n"
        return output

    @property
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

    @property
    def is_healthy(self):
        return bool([item for item in self.status if item.get("type") == "cluster"][0]["quorate"])

    def get_vm(self, vm_id):
        if isinstance(vm_id, str):
            vm_id = int(vm_id)

        result = None
        node_name = None
        for vm in self.resources_vms:
            if vm["vmid"] == vm_id:
                node_name = vm["node"]
                break

        for node in self.nodes:
            if node.node == node_name:
                result = [v for v in node.vms if v.vmid == vm_id][0]
                break

        return result

    @property
    def resources_nodes(self):
        return [resource for resource in self.resources if resource["type"] == "node"]

    @property
    def resources_vms(self):
        return [resource for resource in self.resources if resource["type"] == "qemu"]

    @property
    def resources_storages(self):
        return [resource for resource in self.resources if resource["type"] == "storage"]

    def get_storage(self, storage_name):
        return next(filter(lambda s: s.storage == storage_name, self.storages), None)

    @property
    def cpu_metrics(self):
        nodes = self.resources_nodes
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

    @property
    def memory_metrics(self):
        nodes = self.resources_nodes
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

    @property
    def disk_metrics(self):
        storages = self.resources_storages
        total_disk = sum(node.get("maxdisk", 0) for node in storages)
        total_disk_usage = sum(node.get("disk", 0) for node in storages)
        disk_percent = total_disk_usage / total_disk * 100

        return {
            "total": total_disk,
            "usage": total_disk_usage,
            "percent": disk_percent,
        }

    @property
    def metrics(self):
        return {
            "cpu": self.cpu_metrics,
            "memory": self.memory_metrics,
            "disk": self.disk_metrics,
        }

    @property
    def backups(self):
        if self._backups is None:
            self._backups = []
            for item in PVEStorage.get_grouped_list(self):
                for backup in item["storage"].get_content("backup"):
                    self._backups.append(
                        PVEVolume(backup.pop("volid"), backup.pop("format"), backup.pop("size"), **backup)
                    )
        return self._backups

    @property
    def backup_jobs(self):
        if self._backup_jobs is None:
            self._backup_jobs = []
            for backup_job in self.api.cluster.backup.get():
                self._backup_jobs.append(PVEBackupJob(backup_job.pop("id"), **backup_job))
        return self._backup_jobs
