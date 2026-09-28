from dataclasses import dataclass, field

from pvecontrol.models import api_kwargs

VALID_TYPES = ("user", "group", "token")

COLUMNS = ["path", "type", "ugid", "roleid", "propagate"]


@dataclass
class PVEAclData:
    path: str = field(default="")
    type: str = field(default="")
    ugid: str = field(default="")
    roleid: str = field(default="")
    propagate: int = field(default=0)


class PVEAcl(PVEAclData):
    """Proxmox VE ACL entry"""

    def __init__(self, path=None, type=None, ugid=None, roleid=None, **kwargs):  # pylint: disable=redefined-builtin
        super().__init__(path=path, type=type, ugid=ugid, roleid=roleid, **kwargs)

        if not self.path:
            raise ValueError("Invalid path: must be a non-empty string")
        if self.type not in VALID_TYPES:
            raise ValueError(f"Invalid type '{self.type}': must be one of {VALID_TYPES}")
        if not self.ugid:
            raise ValueError("Invalid ugid: must be a non-empty string")
        if not self.roleid:
            raise ValueError("Invalid roleid: must be a non-empty string")

        self.propagate = bool(self.propagate)

    @classmethod
    def from_api(cls, payload):
        return cls(**api_kwargs(PVEAclData, payload))

    def __str__(self):
        return f"PVEAcl({self.path}, {self.type}, {self.ugid}, {self.roleid})"
