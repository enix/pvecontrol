COLUMNS = ["userid", "firstname", "lastname", "email", "realm_type", "enable", "expire", "groups"]


class PVEUser:
    """Proxmox VE User"""

    _default_kwargs = {
        "enable": 1,
        "expire": 0,
        "firstname": "",
        "lastname": "",
        "email": "",
        "realm-type": "",
        "groups": "",
    }

    def __init__(self, userid, **kwargs):
        if not userid or "@" not in userid:
            raise ValueError(f"Invalid userid '{userid}': must be in the form 'username@realm'")
        self.userid = userid

        enable = kwargs.get("enable", self._default_kwargs["enable"])
        if enable not in (0, 1):
            raise ValueError(f"Invalid enable value '{enable}' for user '{userid}': must be 0 or 1")
        self.enable = bool(enable)

        expire = kwargs.get("expire", self._default_kwargs["expire"])
        if not isinstance(expire, int) or expire < 0:
            raise ValueError(f"Invalid expire value '{expire}' for user '{userid}': must be a non-negative integer")
        self.expire = expire

        self.firstname = kwargs.get("firstname", "")
        self.lastname = kwargs.get("lastname", "")
        self.email = kwargs.get("email", "")
        self.realm_type = kwargs.get("realm-type", "")

        groups = kwargs.get("groups", "")
        if isinstance(groups, str):
            self.groups = [g for g in groups.split(",") if g]
        else:
            self.groups = list(groups)

    def get_groups(self, proxmox):
        """Return PVEGroup objects for each group this user belongs to."""
        return [group for group in proxmox.groups if group.groupid in self.groups]

    def __str__(self):
        return f"PVEUser({self.userid})"
