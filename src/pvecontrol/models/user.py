COLUMNS = ["userid", "firstname", "lastname", "email", "realm_type", "enable", "expire", "groups", "tokens"]


class PVEUser:
    """Proxmox VE User"""

    _default_kwargs = {
        "enable": 1,
        "expire": 0,
        "firstname": "",
        "lastname": "",
        "email": "",
        "realm_type": "",
        "groups": "",
    }

    # pylint: disable=access-member-before-definition
    def __init__(self, userid, **kwargs):
        if not userid or "@" not in userid:
            raise ValueError(f"Invalid userid '{userid}': must be in the form 'username@realm'")
        self.userid = userid

        for k, v in self._default_kwargs.items():
            self.__setattr__(k, kwargs.get(k, v))

        if self.enable not in (0, 1):
            raise ValueError(f"Invalid enable value '{self.enable}' for user '{userid}': must be 0 or 1")
        self.enable = bool(self.enable)

        if not isinstance(self.expire, int) or self.expire < 0:
            raise ValueError(
                f"Invalid expire value '{self.expire}' for user '{userid}': must be a non-negative integer"
            )

        if isinstance(self.groups, str):
            self.groups = [g for g in self.groups.split(",") if g]
        else:
            self.groups = list(self.groups)

        tokens = kwargs.get("tokens") or []
        self.tokens = [f"{self.userid}!{t['tokenid']}" for t in tokens if "tokenid" in t]

    def get_groups(self, proxmox):
        """Return PVEGroup objects for each group this user belongs to."""
        return [group for group in proxmox.groups if group.groupid in self.groups]

    def __str__(self):
        return f"PVEUser({self.userid})"
