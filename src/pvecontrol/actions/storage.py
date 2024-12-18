from pvecontrol.storage import PVEStorage, COLUMNS
from pvecontrol.utils import print_tableoutput


def action_storagelist(proxmox, args):
    """Describe cluster storages"""
    storages = PVEStorage.get_grouped_list(proxmox)

    for item in storages:
        storage = item.pop("storage").__dict__
        storage.pop("node")
        item.update(storage)

    for storage in storages:
        storage["nodes"] = ", ".join(storage["nodes"])

    print_tableoutput(storages, COLUMNS, sortby=args.sort_by, filters=args.filter)
