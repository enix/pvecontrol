from dataclasses import dataclass, field
from typing import List, Union

from pvecontrol.models import api_kwargs

COLUMNS = ["groupid", "comment", "users"]


@dataclass
class PVEGroupData:
    groupid: str = field(default="")
    comment: str = field(default="")
    users: Union[str, List[str]] = field(default="")


class PVEGroup(PVEGroupData):
    """Proxmox VE Access Group"""

    def __init__(self, groupid=None, **kwargs):
        super().__init__(groupid=groupid, **api_kwargs(PVEGroupData, kwargs))

        if not self.groupid:
            raise ValueError("Invalid groupid: must be a non-empty string")

        if isinstance(self.users, str):
            self.users = [u for u in self.users.split(",") if u]
        else:
            self.users = list(self.users)

    def get_members(self, proxmox):
        """Return PVEUser objects for each member of this group."""
        return [user for user in proxmox.users if user.userid in self.users]

    def __str__(self):
        return f"PVEGroup({self.groupid})"
