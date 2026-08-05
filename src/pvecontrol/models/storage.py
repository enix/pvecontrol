import logging
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Optional

from pvecontrol.models import api_kwargs, format_fields
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

    def __str__(self):
        return STORAGE_SHARED_ENUM[self.value]


@dataclass
class PVEStorageData:
    node: str = field(default="")
    id: str = field(default="")
    shared: Optional[StorageShared] = None
    type: str = field(default="")
    storage: str = field(default="")
    maxdisk: int = field(default=0)
    disk: int = field(default=0)
    plugintype: str = field(default="")
    status: str = field(default="")
    content: str = field(default="")


class PVEStorage(PVEStorageData):
    """Proxmox VE Storage"""

    _api = None

    def __init__(self, api, **kwargs):
        super().__init__(**kwargs)
        self.short_id = self.id.rsplit("/", maxsplit=1)[-1]
        self._api = api
        self._content = {}
        self.shared = StorageShared(int(self.shared or 0))
        # We exclude s3 storage type sizing informations wich are not relevent.
        # PVE api see missleading informations depending on s3 tool used to mount the filesystem thru fuse.
        if self.plugintype == "s3":
            self.disk = 0
            self.maxdisk = 0

    @classmethod
    def from_api(cls, api, payload):
        return cls(api, **api_kwargs(PVEStorageData, payload))

    @staticmethod
    def get_grouped_list(proxmox, online_only=False):
        storages = {}
        for storage in proxmox.storages:
            if online_only and not proxmox.is_node_online(storage.node):
                continue
            value = {"storage": storage, "nodes": [], "usage": f"{storage.percentage:.1f}%"}
            if storage.shared == StorageShared.SHARED:
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
        """One plain dict per grouped storage, built from the public fields of its representative.

        The PVEStorage objects are left untouched, so they stay usable afterwards.
        """
        rows = []
        for item in PVEStorage.get_grouped_list(proxmox):
            storage = item["storage"]
            row = {f.name: getattr(storage, f.name) for f in fields(PVEStorageData)}
            row.update(
                {
                    "shared": str(storage.shared),
                    "nodes": ", ".join(item["nodes"]),
                    "usage": item["usage"],
                }
            )
            if not proxmox.is_node_online(storage.node):
                # cluster/resources keeps the last known status, or none
                row["status"] = "unknown"
            rows.append(row)

        return rows

    @property
    def percentage(self):
        return self.disk / self.maxdisk * 100 if self.maxdisk else 0

    @property
    def images(self):
        return [PVEVolume.from_api(image) for image in self.get_content("images")]

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
        return format_fields(self)
