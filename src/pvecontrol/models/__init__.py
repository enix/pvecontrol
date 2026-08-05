from dataclasses import fields


def api_kwargs(dataclass_type, kwargs):
    """Keep only the keys of an API payload that map to a field of dataclass_type.

    The Proxmox API uses dashes in some of its keys ("next-run", "prune-backups"),
    which are not valid python identifiers: those are translated to underscores.
    """
    names = {f.name for f in fields(dataclass_type)}
    values = {}
    for key, value in kwargs.items():
        name = key.replace("-", "_")
        if name in names:
            values[name] = value
    return values


def format_fields(instance):
    """Render the dataclass fields of an instance, one "Key: value" per line.

    Underscores are turned back into dashes so the output keeps using the api wording.
    """
    return "\n".join(f"{f.name.replace('_', '-').capitalize()}: {getattr(instance, f.name)}" for f in fields(instance))
