from pvecontrol.storage import StorageShared, COLUMNS
from pvecontrol.utils import print_output


def action_storagelist(proxmox, args):
    """Describe cluster storages"""
    storages = {}
    for storage in proxmox.storages:
        d = storage.__dict__
        node = d.pop("node")
        value = {**d, "nodes": [], "usage": f"{storage.percentage:.1f}%"}
        if StorageShared[storage.shared.upper()] == StorageShared.SHARED:
            storages[storage.storage] = storages.get(storage.storage, value)
            storages[storage.storage]["nodes"] += [node]
        else:
            storages[storage.id] = value
            storages[storage.id]["nodes"] += [node]

    for _id, storage in storages.items():
        storage["nodes"] = ", ".join(storage["nodes"])

    print_output(storages.values(), COLUMNS, sortby=args.sort_by, filters=args.filter, output=args.output)
