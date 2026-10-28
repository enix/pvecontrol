import logging
import fnmatch
import sys

from proxmoxer import ProxmoxAPI
from proxmoxer.core import AuthenticationError, ResourceException
from proxmoxer.tools import Tasks
from requests.exceptions import ConnectionError as RequestsConnectionError, SSLError, Timeout

from pvecontrol.utils import defaulter, run_auth_commands
from pvecontrol.models.node import PVENode
from pvecontrol.models.storage import PVEStorage
from pvecontrol.models.task import PVETask
from pvecontrol.models.acl import PVEAcl
from pvecontrol.models.backup_job import PVEBackupJob
from pvecontrol.models.group import PVEGroup
from pvecontrol.models.user import PVEUser
from pvecontrol.models.volume import PVEVolume
from pvecontrol.config import set_config


# FIXME: remove pylint disable annotations
# pylint: disable=too-many-public-methods
class PVECluster:
    """Proxmox VE Cluster"""

    def __init__(self, name, host, config, timeout, verify_ssl=False, **auth):
        self.name = name
        self.config = config
        self._tasks = None
        self._ha = None
        self._backups = None
        self._backup_jobs = None
        self._users = None
        self._groups = None
        self._acls = None
        # With a password, ProxmoxAPI authenticates right away; with a token, the first call does
        try:
            self.api = ProxmoxAPI(host, timeout=timeout, verify_ssl=verify_ssl, **auth)
            self._initstatus()
        except (RequestsConnectionError, Timeout, AuthenticationError, ResourceException) as e:
            message = _connection_error_message(host, timeout, auth, e)
            if message is None:
                raise
            logging.debug("Connection to %s failed", host, exc_info=True)
            logging.error(message)
            sys.exit(1)

    def _initstatus(self):
        self.version = self.api.version.get()
        self.status = self.api.cluster.status.get()
        self.resources = self.api.cluster.resources.get()
        cluster_entry = [item for item in self.status if item.get("type") == "cluster"][0]
        self.cluster_name = str(cluster_entry["name"])

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
        for resource in self.resources_storages:
            # Work on a copy: the cluster/resources entry keeps its node, id and shared keys
            storage = dict(resource)
            self.storages.append(
                PVEStorage(self.api, storage.pop("node"), storage.pop("id"), storage.pop("shared"), **storage)
            )

    @staticmethod
    def create_from_config(cluster_name):
        logging.info("Proxmox cluster: %s", cluster_name)

        clusterconfig = set_config(cluster_name)
        auth = run_auth_commands(clusterconfig)
        proxmoxcluster = PVECluster(
            clusterconfig.name,
            clusterconfig.host,
            config={"node": clusterconfig.node, "vm": clusterconfig.vm},
            verify_ssl=clusterconfig.ssl_verify,
            timeout=clusterconfig.timeout,
            **auth,
        )

        return proxmoxcluster

    @property
    def ha(self):
        if self._ha is not None:
            return self._ha

        # use rules instead of ha in newer versions
        if float(self.version["release"]) >= 9.1:
            _ha_groups = self.api.cluster.ha.rules.get()
        else:
            _ha_groups = self.api.cluster.ha.groups.get()
        self._ha = {
            "groups": _ha_groups,
            "manager_status": self.api.cluster.ha.status.manager_status.get(),
            "resources": self.api.cluster.ha.resources.get(),
        }
        return self._ha

    @property
    def tasks(self):
        if self._tasks is not None:
            return self._tasks

        # cluster/tasks holds the status of every task: no need for one call per task to its node
        self._tasks = []
        for task in self.api.cluster.tasks.get():
            logging.debug("Get task informations: %s", (str(task)))
            node_online = self.is_node_online(task["node"])
            self._tasks.append(PVETask(self.api, task["upid"], summary=task, node_online=node_online))
        return self._tasks

    def refresh(self):
        self._initstatus()

        # tasks are fetched again on next use
        self._tasks = None

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

    def is_node_online(self, nodename):
        """Only the API calls proxied to an online node can succeed"""
        node = self.find_node(nodename)
        return bool(node) and node.online

    def find_nodes(self, pattern):
        """Find a list of nodes running on this cluster based on a glob pattern"""
        nodes = []
        for node in self.nodes:
            if fnmatch.fnmatchcase(node.node, pattern):
                nodes.append(node)
        return nodes

    def get_task(self, upid):
        """Return a task with its current status, or None if it can't be found"""
        node = Tasks.decode_upid(upid)["node"]
        if self.is_node_online(node):
            # A task started a moment ago may not be listed in cluster/tasks yet, its node knows it
            return PVETask(self.api, upid)
        # The node can't answer, cluster/tasks is the only source left
        return next((task for task in self.tasks if task.upid == upid), None)

    @property
    def is_healthy(self):
        return bool([item for item in self.status if item.get("type") == "cluster"][0]["quorate"])

    def get_vm(self, vm_id):
        if isinstance(vm_id, str):
            vm_id = int(vm_id)

        return next((vm for vm in self.vms if vm.vmid == vm_id), None)

    @property
    def resources_nodes(self):
        return [
            defaulter(resource, ["cpu", "mem", "maxmem", "maxcpu", "disk", "maxdisk"], 0)
            for resource in self.resources
            if resource["type"] == "node"
        ]

    @property
    def resources_vms(self):
        return [
            defaulter(resource, ["maxcpu", "maxdisk", "maxmem"], 0)
            for resource in self.resources
            if resource["type"] == "qemu"
        ]

    @property
    def resources_storages(self):
        return [
            defaulter(resource, ["disk", "maxdisk"], 0) for resource in self.resources if resource["type"] == "storage"
        ]

    def get_storage(self, storage_name):
        return next(filter(lambda s: s.storage == storage_name, self.storages), None)

    @property
    def cpu_metrics(self):
        # A node that is not online provides no capacity, and its usage is missing or stale
        nodes = [node for node in self.resources_nodes if self.is_node_online(node["node"])]
        total_cpu = sum(node["maxcpu"] for node in nodes)
        total_cpu_usage = sum(node["cpu"] for node in nodes)
        total_cpu_allocated = sum(node.allocatedcpu for node in self.nodes)
        cpu_percent = total_cpu_usage / total_cpu * 100 if total_cpu else 0

        return {
            "total": total_cpu,
            "usage": total_cpu_usage,
            "allocated": total_cpu_allocated,
            "percent": cpu_percent,
        }

    @property
    def memory_metrics(self):
        # A node that is not online provides no capacity, and its usage is missing or stale
        nodes = [node for node in self.resources_nodes if self.is_node_online(node["node"])]
        total_memory = sum(node["maxmem"] for node in nodes)
        total_memory_usage = sum(node["mem"] for node in nodes)
        total_memory_allocated = sum(node.allocatedmem for node in self.nodes)
        memory_percent = total_memory_usage / total_memory * 100 if total_memory else 0

        return {
            "total": total_memory,
            "usage": total_memory_usage,
            "allocated": total_memory_allocated,
            "percent": memory_percent,
        }

    @property
    def disk_metrics(self):
        # The usage of a storage seen through a node that is not online is missing or stale
        storages = [storage for storage in self.resources_storages if self.is_node_online(storage["node"])]
        total_disk = sum(node["maxdisk"] for node in storages)
        total_disk_usage = sum(node["disk"] for node in storages)
        disk_percent = total_disk_usage / total_disk * 100 if total_disk else 0

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
            # A shared storage is listed through one of its nodes: it must be one that can answer
            for item in PVEStorage.get_grouped_list(self, online_only=True):
                logging.debug("Find storage: %s", (str(item)))
                for backup in item["storage"].get_content("backup"):
                    logging.debug("New vm backup: %s", (str(backup)))
                    self._backups.append(
                        PVEVolume(backup.pop("volid"), backup.pop("format"), backup.pop("size"), **backup)
                    )
        return self._backups

    @property
    def acls(self):
        if self._acls is None:
            self._acls = [PVEAcl(**entry) for entry in self.api.access.acl.get()]
        return self._acls

    @property
    def groups(self):
        if self._groups is None:
            self._groups = [PVEGroup(**g) for g in self.api.access.groups.get()]
        return self._groups

    @property
    def users(self):
        if self._users is None:
            self._users = [PVEUser(**u) for u in self.api.access.users.get(full=1)]
        return self._users

    @property
    def backup_jobs(self):
        if self._backup_jobs is None:
            self._backup_jobs = []
            for backup_job in self.api.cluster.backup.get():
                logging.debug("New backup job: %s", (str(backup_job)))
                self._backup_jobs.append(PVEBackupJob(backup_job.pop("id"), **backup_job))
        return self._backup_jobs


def _connection_error_message(host, timeout, auth, error):
    """Explain why the cluster can't be reached, or None when the error is not about reaching it"""
    # requests wraps the urllib3 error, whose reason is the readable part
    reason = getattr(error.args[0], "reason", error) if error.args else error
    user = auth.get("user", "")
    if "token_name" in auth:
        user = f"{user}!{auth['token_name']}"

    if isinstance(error, SSLError):
        return f"TLS error with {host}: {reason}"
    if isinstance(error, Timeout):
        return f"Connection to {host} timed out after {timeout}s"
    if isinstance(error, RequestsConnectionError):
        return f"Can't connect to {host}: {reason}"
    if isinstance(error, AuthenticationError) or (isinstance(error, ResourceException) and error.status_code == 401):
        return f"Authentication failed on {host} for {user}"
    return None
