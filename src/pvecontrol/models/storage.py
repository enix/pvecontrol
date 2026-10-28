import logging
from enum import Enum

from pvecontrol.models.volume import PVEVolume

STORAGE_SHARED_ENUM = ["local", "shared"]
COLUMNS = [
    "storage",
    "nodes",
    "shared",
    "usage",
    "maxdisk",
    "disk",
    "plugintype",
    "status",
]


class StorageShared(Enum):
    LOCAL = 0
    SHARED = 1


class PVEStorage:
    """Proxmox VE Storage"""

    _default_kwargs = {
        "storage": None,
        "maxdisk": None,
        "disk": None,
        "plugintype": None,
        "status": None,
        "test": None,
    }

    def __init__(self, api, node, storage_id, shared, **kwargs):
        self.id = storage_id
        self.short_id = storage_id.split("/")[-1]
        self.node = node
        self._api = api
        self._content = {}
        self._details = {}

        self.shared = STORAGE_SHARED_ENUM[shared]

        for k, v in self._default_kwargs.items():
            self.__setattr__(k, kwargs.get(k, v))
        # We exclude s3 storage type sizing informations wich are not relevent.
        # PVE api see missleading informations depending on s3 tool used to mount the filesystem thru fuse.
        if self.plugintype == "s3":
            self.disk = 0
            self.maxdisk = 0

    @property
    def details(self):
        if self._details is None:
            self._details = self._api.storage(self.short_id).get()

        return self._details

    @staticmethod
    def get_grouped_list(proxmox, online_only=False):
        storages = {}
        for storage in proxmox.storages:
            if online_only and not proxmox.is_node_online(storage.node):
                continue
            value = {"storage": storage, "nodes": [], "usage": f"{storage.percentage:.1f}%"}
            if StorageShared[storage.shared.upper()] == StorageShared.SHARED:
                group = storages.setdefault(storage.storage, value)
                # The entry of a node that is not online holds stale or missing usage data
                if not proxmox.is_node_online(group["storage"].node) and proxmox.is_node_online(storage.node):
                    group["storage"] = storage
                    group["usage"] = value["usage"]
                group["nodes"] += [storage.node]
            else:
                storages[storage.id] = value
                storages[storage.id]["nodes"] += [storage.node]

        for group in storages.values():
            # No online node can tell the current usage of this storage
            if not proxmox.is_node_online(group["storage"].node):
                group["usage"] = "unknown"

        return storages.values()

    @staticmethod
    def get_flattened_grouped_list(proxmox):
        storages = PVEStorage.get_grouped_list(proxmox)

        for item in storages:
            storage = item.pop("storage").__dict__
            node = storage.pop("node")
            item.update(storage)
            if not proxmox.is_node_online(node):
                # cluster/resources keeps the last known status, or none
                item["status"] = "unknown"

        for storage in storages:
            storage["nodes"] = ", ".join(storage["nodes"])

        return storages

    @property
    def percentage(self):
        return self.disk / self.maxdisk * 100 if self.maxdisk else 0

    @property
    def images(self):
        images = []
        for image in self.get_content("images"):
            images.append(PVEVolume(image.pop("volid"), image.pop("format"), image.pop("size"), **image))
        return images

    def get_content(self, content_type=None):
        if content_type not in self._content:
            try:
                self._content[content_type] = (
                    self._api.nodes(self.node).storage(self.short_id).content.get(content=content_type)
                )
            except Exception:  # pylint: disable=broad-except
                logging.warning(
                    "Could not get content '%s' for storage %s on %s", content_type, self.storage, self.node
                )
                self._content[content_type] = []
        return self._content[content_type]

    def __str__(self):
        output = f"Node: {self.node}\n" + f"Id: {self.id}\n"
        for key in self._default_kwargs:
            output += f"{key.capitalize()}: {self.__getattribute__(key)}\n"
        return output
