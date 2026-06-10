import logging
import sys

from proxmoxer import ProxmoxAPI
from requests.exceptions import SSLError

from pvecontrol.utils import run_auth_commands
from pbscontrol.config import set_config


class PBSServer:
    """Proxmox Backup Server"""

    def __init__(self, name, host, port, timeout, verify_ssl=False, **auth):
        try:
            self.api = ProxmoxAPI(host, port=port, timeout=timeout, verify_ssl=verify_ssl, service="pbs", **auth)
        except SSLError as e:
            print(e)
            sys.exit(1)
        self.name = name
        self._initstatus()

    def _initstatus(self):
        self.version = self.api.version.get()
        self.datastores = self.api.admin.datastore.get()

    @staticmethod
    def create_from_config(server_name):
        logging.info("Proxmox Backup Server: %s", server_name)

        serverconfig = set_config(server_name)
        auth = run_auth_commands(serverconfig)
        return PBSServer(
            serverconfig.name,
            serverconfig.host,
            port=serverconfig.port,
            verify_ssl=serverconfig.ssl_verify,
            timeout=serverconfig.timeout,
            **auth,
        )

    @property
    def datastore_usage(self):
        usage = []
        for ds in self.datastores:
            store = ds.get("store")
            try:
                status = self.api.admin.datastore(store).status.get()
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.warning("Could not get status for datastore %s: %s", store, e)
                status = {}
            usage.append(
                {
                    "store": store,
                    "total": status.get("total", 0),
                    "used": status.get("used", 0),
                    "avail": status.get("avail", 0),
                    "gc-status": status.get("gc-status", {}).get("error", "ok"),
                }
            )
        return usage
