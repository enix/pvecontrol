from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

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


@dataclass
class PVEStorageData:
    api: object = None
    node: str = field(default="")
    id: str = field(default="")
    shared: Optional["StorageShared"] = None
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
        if isinstance(self.id, str):
            self.short_id = self.id.rsplit("/", maxsplit=1)[-1]
        self._api = api
        self._content = {}
        self._details = {}
        self.shared = StorageShared[STORAGE_SHARED_ENUM[self.shared].upper()]

    @property
    def details(self):
        if self._details is None:
            self._details = self._api.storage(self.short_id).get()

        return self._details

    @staticmethod
    def get_grouped_list(proxmox):
        storages = {}
        for storage in proxmox.storages:
            value = {"storage": storage, "nodes": [], "usage": f"{storage.percentage:.1f}%"}
            if storage.shared == StorageShared.SHARED:
                storages[storage.storage] = storages.get(storage.storage, value)
                storages[storage.storage]["nodes"] += [storage.node]
            else:
                storages[storage.id] = value
                storages[storage.id]["nodes"] += [storage.node]

        return storages.values()

    @staticmethod
    def get_flattened_grouped_list(proxmox):
        storages = PVEStorage.get_grouped_list(proxmox)

        for item in storages:
            storage = item.pop("storage").__dict__
            storage.pop("node")
            item.update(storage)

        for storage in storages:
            storage["nodes"] = ", ".join(storage["nodes"])

        return storages

    @property
    def percentage(self):
        return self.disk / self.maxdisk * 100 if self.maxdisk else 0

    @property
    def images(self):
        return [PVEVolume(**image) for image in self.get_content("images")]

    def get_content(self, content_type=None):
        if content_type not in self._content:
            self._content[content_type] = (
                self._api.nodes(self.node).storage(self.short_id).content.get(content=content_type)
            )
        return self._content[content_type]

    def __str__(self):
        output = f"Node: {self.node}\n" + f"Id: {self.id}\n"
        for key in self._default_kwargs:
            output += f"{key.capitalize()}: {self.__getattribute__(key)}\n"
        return output
