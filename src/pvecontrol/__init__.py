#!/usr/bin/env python3

import sys
import logging
import re
import subprocess
import json

from types import SimpleNamespace
from importlib.metadata import version

import urllib3
import click

from pvecontrol import actions
from pvecontrol.config import set_config
from pvecontrol.models.cluster import PVECluster
from pvecontrol.utils import OutputFormats


def _execute_command(cmd):
    return subprocess.run(cmd, shell=True, check=True, capture_output=True).stdout.rstrip()


def run_auth_commands(clusterconfig):
    auth = {}
    regex = r"^\$\((.*)\)$"

    keys = ["user", "password", "token_name", "token_value"]

    if clusterconfig["proxy_certificate"] is not None:
        if isinstance(clusterconfig.get("proxy_certificate"), str):
            keys.append("proxy_certificate")
        else:
            auth["proxy_certificate"] = clusterconfig["proxy_certificate"]

    for key in keys:
        value = clusterconfig.get(key)
        if value is not None:
            result = re.match(regex, value)
            if result:
                value = _execute_command(result.group(1))
            auth[key] = value

    if "proxy_certificate" in auth and isinstance(auth["proxy_certificate"], bytes):
        proxy_certificate = json.loads(auth["proxy_certificate"])
        auth["proxy_certificate"] = {
            "cert": proxy_certificate.get("cert"),
            "key": proxy_certificate.get("key"),
        }

    if "proxy_certificate" in auth:
        auth["cert"] = (auth["proxy_certificate"]["cert"], auth["proxy_certificate"]["key"])
        del auth["proxy_certificate"]

    logging.debug("Auth: %s", auth)
    # check for "incompatible" auth options
    if "password" in auth and ("token_name" in auth or "token_value" in auth):
        logging.error("Auth: cannot use both password and token options together.")
        sys.exit(1)
    if "token_name" in auth and "token_value" not in auth:
        logging.error("Auth: token-name requires token-value option.")
        sys.exit(1)

    return auth


# Patch click to ignore required parameters when --help is passed
class IgnoreRequiredForHelp(click.Group):
    def parse_args(self, ctx, args):
        self.ignoring = False
        try:
            return super(IgnoreRequiredForHelp, self).parse_args(ctx, args)
        except click.MissingParameter:
            if "--help" not in args:
                raise
            self.ignoring = True
            for param in self.params:
                param.required = False
            return super(IgnoreRequiredForHelp, self).parse_args(ctx, args)


@click.group(
    cls=IgnoreRequiredForHelp,
    help=f"Proxmox VE control CLI, version: {version(__name__)}",
    epilog="Made with love by Enix.io",
)
@click.option("-d", "--debug", is_flag=True)
@click.option(
    "-o",
    "--output",
    type=click.Choice([o.value for o in OutputFormats]),
    show_default=True,
    default=OutputFormats.TEXT.value,
    callback=lambda *v: OutputFormats(v[2]),
)
@click.option("-c", "--cluster", required=True, help="Proxmox cluster name as defined in configuration")
@click.pass_context
def main(ctx, debug, output, cluster):
    if not ctx.command.ignoring:
        # Disable urllib3 warnings about invalid certs
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # get cli arguments
        args = SimpleNamespace(debug=debug, output=output, cluster=cluster)

        # configure logging
        logging.basicConfig(encoding="utf-8", level=logging.DEBUG if args.debug else logging.INFO)
        logging.debug("Arguments: %s", args)
        logging.info("Proxmox cluster: %s", args.cluster)

        clusterconfig = set_config(args.cluster)
        auth = run_auth_commands(clusterconfig)
        proxmoxcluster = PVECluster(
            clusterconfig.name,
            clusterconfig.host,
            config={"node": clusterconfig.node, "vm": clusterconfig.vm},
            verify_ssl=clusterconfig.ssl_verify,
            timeout=clusterconfig.timeout,
            **auth,
        )
        ctx.ensure_object(dict)
        ctx.obj["cluster"] = proxmoxcluster
        ctx.obj["args"] = args


main.add_command(cmd=actions.cluster.status, name="status")
main.add_command(cmd=actions.cluster.sanitycheck, name="sanitycheck")
main.add_command(cmd=actions.node.root, name="node")
main.add_command(cmd=actions.storage.root, name="storage")
main.add_command(cmd=actions.task.root, name="task")
main.add_command(cmd=actions.vm.root, name="vm")
if __name__ == "__main__":
    sys.exit(main())
