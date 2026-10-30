#!/usr/bin/env python3

import sys
import logging
import signal

from types import SimpleNamespace
from importlib.metadata import version

import click
import confuse
import urllib3

from pvecontrol import actions
from pvecontrol.config import config, list_clusters
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
    if isinstance(sub_cmd, click.Group) and len(sub_args) > 0:
        sub_ctx = sub_cmd.make_context(name, sub_args, parent=ctx)
        return get_leaf_command(sub_cmd, sub_ctx, sub_args)

    return sub_cmd, sub_args


# Key of ctx.meta telling that the invocation only displays a help, see IgnoreRequiredForHelp
HELP_ONLY = "pvecontrol.help_only"


def is_help_only(ctx):
    """Tell whether the invocation only displays a help, in which case the group callback must not load any config"""
    return ctx.meta.get(HELP_ONLY, False)


# Patch click to ignore required parameters when --help is passed
class IgnoreRequiredForHelp(click.Group):
    """Let --help work on any subcommand without the options the group requires, --cluster for instance.

    The state lives in the invocation context, never in the group itself: the group is a module-level
    object shared by every invocation in a process (the test suite runs many of them).
    """

    def _is_defaulting_to_help(self, ctx, args):
        try:
            leaf_cmd, leaf_args = get_leaf_command(self, ctx, args)

            # keep the default behavior when no subcommand is passed or when the subcommand doesn't exists
            if leaf_cmd is None or leaf_cmd is self:
                return False

            return (
                "--help" in leaf_args
                or (isinstance(leaf_cmd, click.Group) and not leaf_cmd.invoke_without_command)
                or (leaf_cmd.no_args_is_help and len(leaf_args) == 0)
            )
        except click.exceptions.UsageError:
            return False

    def parse_args(self, ctx, args):
        ctx.meta[HELP_ONLY] = self._is_defaulting_to_help(ctx, args)
        if not ctx.meta[HELP_ONLY]:
            return super().parse_args(ctx, args)

        # Relax the required parameters for this parsing only
        required = [param for param in self.params if param.required]
        for param in required:
            param.required = False
        try:
            return super().parse_args(ctx, args)
        finally:
            for param in required:
                param.required = True

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
                if not isinstance(cmd, click.Group):
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
    default=None,
    help="Proxmox cluster name as defined in configuration",
)
@click.option(
    "--unicode/--no-unicode",
    envvar="UNICODE",
    default=True,
    help="Use unicode characters for output",
)
@click.option(
    "--color/--no-color",
    envvar="COLOR",
    default=True,
    help="Use colorized output",
)
@click.option(
    "--config",
    "config_file",
    metavar="PATH",
    envvar="CONFIG",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help=f"Path to configuration file (overrides default {config.user_config_path()})",
)
@click.pass_context
def pvecontrol(ctx, debug, output, cluster, unicode, color, config_file):
    signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
    # Disable urllib3 warnings about invalid certs
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if not is_help_only(ctx):
        # configure logging
        logging.basicConfig(encoding="utf-8", level=logging.DEBUG if debug else logging.INFO)

        if config_file:
            # Use the given file authoritatively: layer it on top of the packaged
            # defaults only, skipping the user config (~/.config/pvecontrol/config.yaml).
            # confuse merges sources key-by-key, so without this any key absent from
            # the given file (proxy_certificate, timeout, extra clusters, ...) would
            # leak in from the user config. And since the config is a list and not
            # a dict, items of the list will be merged based on their index in the
            # config file, producing very weird behaviors.
            config.read(user=False, defaults=True)
            try:
                config.set_file(config_file)
            except confuse.ConfigReadError as e:
                logging.error("Cannot read configuration file: %s", e)
                ctx.exit(1)

        if cluster is None:
            clusters = list_clusters()
            logging.debug("No cluster specified, found %d cluster(s) in config: %s", len(clusters), clusters)
            if len(clusters) == 1:
                cluster = clusters[0]
                logging.debug("Auto-selected single cluster: %s", cluster)
            elif len(clusters) == 0:
                logging.error("No cluster configured. Please add a cluster to your configuration file.")
                logging.error("Configuration file: %s", config_file or config.user_config_path())
                ctx.exit(1)
            else:
                available = "\n".join(f"  {name}" for name in clusters)
                logging.error(
                    "No cluster specified. Available clusters:\n%s\n\n"
                    "Use -c / --cluster NAME or set the PVECONTROL_CLUSTER environment variable.",
                    available,
                )
                ctx.exit(1)
        else:
            logging.debug("Cluster specified: %s", cluster)

        # get cli arguments
        args = SimpleNamespace(output=output, cluster=cluster, unicode=unicode, color=color)
        logging.debug("Arguments: %s", args)

        ctx.ensure_object(dict)
        ctx.obj["args"] = args


pvecontrol.add_command(cmd=actions.cluster.status, name="status")
pvecontrol.add_command(cmd=actions.cluster.sanitycheck, name="sanitycheck")
pvecontrol.add_command(cmd=actions.report.report, name="report")
pvecontrol.add_command(cmd=actions.node.root, name="node")
pvecontrol.add_command(cmd=actions.storage.root, name="storage")
pvecontrol.add_command(cmd=actions.task.root, name="task")
pvecontrol.add_command(cmd=actions.acl.root, name="acl")
pvecontrol.add_command(cmd=actions.group.root, name="group")
pvecontrol.add_command(cmd=actions.user.root, name="user")
pvecontrol.add_command(cmd=actions.vm.root, name="vm")


def main():
    # pylint: disable=no-value-for-parameter
    pvecontrol(auto_envvar_prefix="PVECONTROL")


if __name__ == "__main__":
    sys.exit(main())
