from dataclasses import dataclass, field
from typing import List, Union

from pvecontrol.models import api_kwargs

COLUMNS = ["userid", "firstname", "lastname", "email", "realm_type", "enable", "expire", "groups", "tokens"]


@dataclass
class PVEUserData:
    userid: str = field(default="")
    enable: int = field(default=1)
    expire: int = field(default=0)
    firstname: str = field(default="")
    lastname: str = field(default="")
    email: str = field(default="")
    # the api key for this one is "realm-type"
    realm_type: str = field(default="")
    groups: Union[str, List[str]] = field(default="")
    tokens: List = field(default_factory=list)


class PVEUser(PVEUserData):
    """Proxmox VE User"""

    def __init__(self, userid=None, **kwargs):
        super().__init__(userid=userid, **kwargs)

        if not self.userid or "@" not in self.userid:
            raise ValueError(f"Invalid userid '{self.userid}': must be in the form 'username@realm'")

        if self.enable not in (0, 1):
            raise ValueError(f"Invalid enable value '{self.enable}' for user '{self.userid}': must be 0 or 1")
        self.enable = bool(self.enable)

        if not isinstance(self.expire, int) or self.expire < 0:
            raise ValueError(
                f"Invalid expire value '{self.expire}' for user '{self.userid}': must be a non-negative integer"
            )

        if isinstance(self.groups, str):
            self.groups = [g for g in self.groups.split(",") if g]
        else:
            self.groups = list(self.groups)

        self.tokens = [f"{self.userid}!{t['tokenid']}" for t in self.tokens or [] if "tokenid" in t]

    @classmethod
    def from_api(cls, payload):
        return cls(**api_kwargs(PVEUserData, payload))

    def get_groups(self, proxmox):
        """Return PVEGroup objects for each group this user belongs to."""
        return [group for group in proxmox.groups if group.groupid in self.groups]

    def __str__(self):
        return f"PVEUser({self.userid})"
