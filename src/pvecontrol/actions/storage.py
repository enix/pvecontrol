from pvecontrol.storage import StorageShared, COLUMNS
from pvecontrol.utils import filter_keys, print_tableoutput


def action_storagelist(proxmox, args):
    """Describe cluster storages"""
    storages = {}
    for storage in proxmox.storages:
        d = storage.__dict__
        node = d.pop("node")
        value = {**d, "nodes": [], "usage": f"{storage.percentage:.1f}%"}
        if StorageShared[storage.shared] == StorageShared.shared:
            storages[storage.storage] = storages.get(storage.storage, value)
            storages[storage.storage]["nodes"] += [node]
        else:
            storages[storage.id] = value
            storages[storage.id]["nodes"] += [node]

    for id, storage in storages.items():
        storages[id]["nodes"] = ", ".join(storages[id]["nodes"])

    print_tableoutput(storages.values(), COLUMNS, sortby=args.sort_by, filters=args.filter)
