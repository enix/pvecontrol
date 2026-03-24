VALID_TYPES = ("user", "group", "token")

COLUMNS = ["path", "type", "ugid", "roleid", "propagate"]


class PVEAcl:
    """Proxmox VE ACL entry"""

    def __init__(self, path, type, ugid, roleid, **kwargs):  # pylint: disable=redefined-builtin
        if not path:
            raise ValueError("Invalid path: must be a non-empty string")
        if type not in VALID_TYPES:
            raise ValueError(f"Invalid type '{type}': must be one of {VALID_TYPES}")
        if not ugid:
            raise ValueError("Invalid ugid: must be a non-empty string")
        if not roleid:
            raise ValueError("Invalid roleid: must be a non-empty string")

        self.path = path
        self.type = type
        self.ugid = ugid
        self.roleid = roleid
        self.propagate = bool(kwargs.get("propagate", 0))

    def __str__(self):
        return f"PVEAcl({self.path}, {self.type}, {self.ugid}, {self.roleid})"
