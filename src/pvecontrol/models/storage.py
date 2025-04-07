from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from pvecontrol.utils import dict_to_attr
from proxmoxer import ProxmoxAPI


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


@dataclass
class PVEStorage:
    """Proxmox VE Storage"""

    api: ProxmoxAPI
    node: str
    storage_id: str
    shared: StorageShared
    kwargs: Dict[str, Any] = field(default_factory=dict)

    storage: Any = field(init=True, default=None)
    maxdisk: int = field(init=True, default=0)
    disk: int = field(init=True, default=0)
    plugintype: str = field(init=True, default="")
    status: str = field(init=True, default="")
    test: str = field(init=True, default="")
    content: dict = field(default_factory=dict)
    type: str = field(init=True, default="")

    def __post_init__(self):
        dict_to_attr(self, 'kwargs')
        self.shared = STORAGE_SHARED_ENUM[self.shared]
        self._content = {}

    @staticmethod
    def get_grouped_list(proxmox):
        storages = {}
        for storage in proxmox.storages:
            value = {"storage": storage, "nodes": [], "usage": f"{storage.percentage:.1f}%"}
            if StorageShared[storage.shared.upper()] == StorageShared.SHARED:
                storages[storage.storage] = storages.get(storage.storage, value)
                storages[storage.storage]["nodes"] += [storage.node]
            else:
                storages[storage.storage_id] = value
                storages[storage.storage_id]["nodes"] += [storage.node]

        return storages.values()

    @property
    def percentage(self):
        return self.disk / self.maxdisk * 100 if self.maxdisk else 0

    def get_content(self, content_type=None):
        if content_type not in self._content:
            short_id = self.storage_id.split("/")[-1]
            self._content[content_type] = self.api.nodes(self.node).storage(short_id).content.get(content=content_type)
        return self._content[content_type]

    def __str__(self):
        output = f"Node: {self.node}\n" + f"Id: {self.storage_id}\n"
        for key in self._default_kwargs:
            output += f"{key.capitalize()}: {self.__getattribute__(key)}\n"
        return output
