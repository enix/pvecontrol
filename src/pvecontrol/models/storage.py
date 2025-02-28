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
            if StorageShared[storage.shared.upper()] == StorageShared.SHARED:
                storages[storage.storage] = storages.get(storage.storage, value)
                storages[storage.storage]["nodes"] += [storage.node]
            else:
                storages[storage.id] = value
                storages[storage.id]["nodes"] += [storage.node]

        return storages.values()

    @property
    def percentage(self):
        if self.maxdisk:
            return self.disk / self.maxdisk * 100
        return 0

    @property
    def images(self):
        images = []
        for image in self.get_content("images"):
            images.append(PVEVolume(image.pop("volid"), image.pop("format"), image.pop("size"), **image))
        return images

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
