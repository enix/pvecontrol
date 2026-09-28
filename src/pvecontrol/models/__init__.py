import logging

from dataclasses import fields


def api_kwargs(dataclass_type, payload):
    """Keep only the keys of an API payload that map to a field of dataclass_type.

    The Proxmox API uses dashes in some of its keys ("next-run", "prune-backups"),
    which are not valid python identifiers: those are translated to underscores.

    This is meant to be called from a model from_api() only: everywhere else the
    keys are ours, and an unknown one is a typo we want to hear about.
    """
    names = {f.name for f in fields(dataclass_type)}
    values = {}
    ignored = []
    for key, value in payload.items():
        name = key.replace("-", "_")
        if name in names:
            values[name] = value
        else:
            ignored.append(key)

    if ignored:
        logging.debug("%s: ignoring api keys %s", dataclass_type.__name__, sorted(ignored))

    return values


def format_fields(instance):
    """Render the dataclass fields of an instance, one "Key: value" per line.

    Underscores are turned back into dashes so the output keeps using the api wording.
    """
    return "\n".join(f"{f.name.replace('_', '-').capitalize()}: {getattr(instance, f.name)}" for f in fields(instance))
