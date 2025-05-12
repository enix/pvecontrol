#!/usr/bin/env python3

import sys
import logging
import signal

from types import SimpleNamespace
from importlib.metadata import version

import click
import urllib3

from pvecontrol import actions
from pvecontrol.utils import OutputFormats


def get_leaf_command(cmd, ctx, args):
    if len(args) == 0:
        return cmd, []

    # remove options from args
    parser = cmd.make_parser(ctx)
    _, args_without_options, _ = parser.parse_args(list(args))

    if len(args_without_options) == 0:
        return cmd, args

    # resolve sub command
    name, sub_cmd, sub_args = cmd.resolve_command(ctx, args_without_options)
    if isinstance(sub_cmd, click.MultiCommand) and len(sub_args) > 0:
        sub_ctx = sub_cmd.make_context(name, sub_args, parent=ctx)
        return get_leaf_command(sub_cmd, sub_ctx, sub_args)

    return sub_cmd, sub_args


# Patch click to ignore required parameters when --help is passed
class IgnoreRequiredForHelp(click.Group):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ignoring = False

    def _is_defaulting_to_help(self, ctx, args):
        try:
            leaf_cmd, leaf_args = get_leaf_command(self, ctx, args)

            # keep the default behavior when no subcommand is passed or when the subcommand doesn't exists
            if leaf_cmd is None or leaf_cmd is self:
                return False

            return (
                "--help" in leaf_args
                or (isinstance(leaf_cmd, click.MultiCommand) and not leaf_cmd.invoke_without_command)
                or (leaf_cmd.no_args_is_help and len(leaf_args) == 0)
            )
        except click.exceptions.UsageError:
            return False

    def parse_args(self, ctx, args):
        if self._is_defaulting_to_help(ctx, args):
            self.ignoring = True
            for param in self.params:
                param.required = False

        return super().parse_args(ctx, args)

    def format_commands(self, ctx, formatter) -> None:
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue

            commands.append((subcommand, cmd))

        if len(commands) > 0:
            limit = formatter.width - 6 - max(len(cmd[0]) for cmd in commands)

            rows = []
            for subcommand, cmd in commands:
                if not isinstance(cmd, click.MultiCommand):
                    cmd_help = cmd.get_short_help_str(limit)
                    rows.append((subcommand, cmd_help))
                    continue
                for subsubcommand in cmd.list_commands(ctx):
                    subcmd = cmd.get_command(ctx, subsubcommand)
                    if subcmd is None or subcmd.hidden:
                        continue
                    cmd_help = subcmd.get_short_help_str(limit)
                    rows.append((f"{subcommand} {subsubcommand}", cmd_help))

            if rows:
                with formatter.section("Commands"):
                    formatter.write_dl(rows)


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
    signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
    # Disable urllib3 warnings about invalid certs
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if not ctx.command.ignoring:
        # get cli arguments
        args = SimpleNamespace(output=output, cluster=cluster)

        # configure logging
        logging.basicConfig(encoding="utf-8", level=logging.DEBUG if debug else logging.INFO)
        logging.debug("Arguments: %s", args)

        ctx.ensure_object(dict)
        ctx.obj["args"] = args


pvecontrol.add_command(cmd=actions.cluster.status, name="status")
pvecontrol.add_command(cmd=actions.cluster.sanitycheck, name="sanitycheck")
pvecontrol.add_command(cmd=actions.cluster_balance.balance, name="balance")
pvecontrol.add_command(cmd=actions.node.root, name="node")
pvecontrol.add_command(cmd=actions.storage.root, name="storage")
pvecontrol.add_command(cmd=actions.task.root, name="task")
pvecontrol.add_command(cmd=actions.vm.root, name="vm")


def main():
    # pylint: disable=no-value-for-parameter
    pvecontrol(auto_envvar_prefix="PVECONTROL")


if __name__ == "__main__":
    sys.exit(main())
