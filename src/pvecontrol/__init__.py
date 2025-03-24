#!/usr/bin/env python3

import sys
import logging

from types import SimpleNamespace
from importlib.metadata import version

import urllib3
import click

from pvecontrol import actions
from pvecontrol.utils import OutputFormats


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
@click.option(
    "-c",
    "--cluster",
    metavar="NAME",
    envvar="CLUSTER",
    required=True,
    help="Proxmox cluster name as defined in configuration",
)
@click.pass_context
def pvecontrol(ctx, debug, output, cluster):
    # Disable urllib3 warnings about invalid certs
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # get cli arguments
    args = SimpleNamespace(debug=debug, output=output, cluster=cluster)

    if not ctx.command.ignoring:

        # configure logging
        logging.basicConfig(encoding="utf-8", level=logging.DEBUG if args.debug else logging.INFO)
        logging.debug("Arguments: %s", args)

        ctx.ensure_object(dict)
        ctx.obj["args"] = args


pvecontrol.add_command(cmd=actions.cluster.status, name="status")
pvecontrol.add_command(cmd=actions.cluster.sanitycheck, name="sanitycheck")
pvecontrol.add_command(cmd=actions.node.root, name="node")
pvecontrol.add_command(cmd=actions.storage.root, name="storage")
pvecontrol.add_command(cmd=actions.task.root, name="task")
pvecontrol.add_command(cmd=actions.vm.root, name="vm")


def main():
    pvecontrol(auto_envvar_prefix="PVECONTROL")


if __name__ == "__main__":
    sys.exit(main())
