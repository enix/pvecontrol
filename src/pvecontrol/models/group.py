COLUMNS = ["groupid", "comment", "users"]


class PVEGroup:
    """Proxmox VE Access Group"""

    def __init__(self, groupid, **kwargs):
        if not groupid:
            raise ValueError("Invalid groupid: must be a non-empty string")
        self.groupid = groupid
        self.comment = kwargs.get("comment", "")

        users = kwargs.get("users", "")
        if isinstance(users, str):
            self.users = [u for u in users.split(",") if u]
        else:
            self.users = list(users)

    def get_members(self, proxmox):
        """Return PVEUser objects for each member of this group."""
        return [user for user in proxmox.users if user.userid in self.users]

    def __str__(self):
        return f"PVEGroup({self.groupid})"
