#!/usr/bin/env python

import sys
import argparse
import logging
import re
import subprocess
import urllib3
import shtab

from pvecontrol import actions, node, vm, task, storage
from pvecontrol.cluster import PVECluster
from pvecontrol.config import set_config
from pvecontrol.utils import OutputFormats


def action_test(proxmox, _args):
    """Hidden optional test action"""
    print(proxmox)


def _make_filter_type_generator(columns):
    def _regexp_type(value):
        try:
            return re.compile(value)
        except re.error as e:
            raise argparse.ArgumentTypeError(f"invalid regular expression: '{value}'", e)

    def _column_type(value):
        if not value in columns:
            choices = ", ".join([f"'{c}'" for c in columns])
            raise argparse.ArgumentTypeError(f"invalid choice: '{value}' (choose from {choices})")
        return value

    while True:
        yield _column_type
        yield _regexp_type


def add_table_related_arguments(parser, columns, default_sort):
    filter_type_generator = _make_filter_type_generator(columns)

    def filter_type(x):
        return next(filter_type_generator)(x)

    parser.add_argument(
        "--sort-by",
        action="store",
        help="Key used to sort items",
        default=default_sort,
        choices=columns,
    )
    parser.add_argument(
        "--filter",
        action="append",
        nargs=2,
        type=filter_type,
        metavar=("COLUMN", "REGEXP"),
        help="Regexp to filter items",
        default=[],
    )
    parser.add_argument(
        "--columns",
        action="store",
        nargs="+",
        help="",
        default=columns,
        choices=columns,
    )


def _parser():
    ## FIXME
    ## Add version in help output

    # Parser configuration
    parser = argparse.ArgumentParser(description="Proxmox VE control cli.", epilog="Made with love by Enix.io")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "-o",
        "--output",
        action="store",
        type=OutputFormats,
        default=OutputFormats.TEXT,
        choices=list(OutputFormats),
    )
    parser.add_argument(
        "-c", "--cluster", action="store", required=True, help="Proxmox cluster name as defined in configuration"
    )
    subparsers = parser.add_subparsers(required=True)

    # clusterstatus parser
    parser_clusterstatus = subparsers.add_parser("clusterstatus", help="Show cluster status")
    parser_clusterstatus.set_defaults(func=actions.cluster.action_clusterstatus)

    # storagelist parser
    parser_storagelist = subparsers.add_parser("storagelist", help="Show cluster status")
    add_table_related_arguments(parser_storagelist, storage.COLUMNS, "storage")
    parser_storagelist.set_defaults(func=actions.storage.action_storagelist)

    # nodelist parser
    parser_nodelist = subparsers.add_parser("nodelist", help="List nodes in the cluster")
    add_table_related_arguments(parser_nodelist, node.COLUMNS, "node")
    parser_nodelist.set_defaults(func=actions.node.action_nodelist)
    # nodeevacuate parser
    parser_nodeevacuate = subparsers.add_parser("nodeevacuate", help="Evacuate an host by migrating all VMs")
    parser_nodeevacuate.add_argument("--node", action="store", required=True, help="Node to evacuate")
    parser_nodeevacuate.add_argument(
        "--target",
        action="append",
        required=False,
        help="Destination Proxmox VE node, you can specify multiple target options",
    )
    parser_nodeevacuate.add_argument("-f", "--follow", action="store_true", help="Follow task log output")
    parser_nodeevacuate.add_argument("-w", "--wait", action="store_true", help="Wait task end")
    parser_nodeevacuate.add_argument(
        "--online", action="store_true", help="Online migrate the VM, default True", default=True
    )
    parser_nodeevacuate.add_argument("--no-skip-stopped", action="store_true", help="Don't skip VMs that are stopped")
    parser_nodeevacuate.add_argument("--dry-run", action="store_true", help="Dry run, do not execute migration")
    parser_nodeevacuate.set_defaults(func=actions.node.action_nodeevacuate)

    # vmlist parser
    parser_vmlist = subparsers.add_parser("vmlist", help="List VMs in the cluster")
    add_table_related_arguments(parser_vmlist, vm.COLUMNS, "vmid")
    parser_vmlist.set_defaults(func=actions.vm.action_vmlist)
    # vmmigrate parser
    parser_vmmigrate = subparsers.add_parser("vmmigrate", help="Migrate VMs in the cluster")
    parser_vmmigrate.add_argument("--vmid", action="store", required=True, type=int, help="VM to migrate")
    parser_vmmigrate.add_argument("--target", action="store", required=True, help="Destination Proxmox VE node")
    parser_vmmigrate.add_argument(
        "--online", action="store_true", help="Online migrate the VM, default True", default=True
    )
    parser_vmmigrate.add_argument("-f", "--follow", action="store_true", help="Follow task log output")
    parser_vmmigrate.add_argument("-w", "--wait", action="store_true", help="Wait task end")
    parser_vmmigrate.add_argument("--dry-run", action="store_true", help="Dry run, do not execute migration")
    parser_vmmigrate.set_defaults(func=actions.vm.action_vmmigrate)

    # tasklist parser
    parser_tasklist = subparsers.add_parser("tasklist", help="List tasks")
    add_table_related_arguments(parser_tasklist, task.COLUMNS, "starttime")
    parser_tasklist.set_defaults(func=actions.task.action_tasklist)
    # taskget parser
    parser_taskget = subparsers.add_parser("taskget", help="Get task detail")
    parser_taskget.add_argument("--upid", action="store", required=True, help="Proxmox tasks UPID to get informations")
    parser_taskget.add_argument("-f", "--follow", action="store_true", help="Follow task log output")
    parser_taskget.add_argument("-w", "--wait", action="store_true", help="Wait task end")
    parser_taskget.set_defaults(func=actions.task.action_taskget)

    # sanitycheck parser
    parser_sanitycheck = subparsers.add_parser("sanitycheck", help="Run Sanity checks on the cluster")
    parser_sanitycheck.add_argument("--check", action="append", required=False, help="Check to run", default=[])
    parser_sanitycheck.set_defaults(func=actions.cluster.action_sanitycheck)

    # _test parser, hidden from help
    parser_test = subparsers.add_parser("_test")
    parser_test.set_defaults(func=action_test)

    # shell autocomplete generation
    shtab.add_argument_to(parser, ["-s", "--print-completion"])

    return parser.parse_args()


def _execute_command(cmd):
    return subprocess.run(cmd, shell=True, check=True, capture_output=True).stdout.rstrip()


def run_auth_commands(clusterconfig):
    auth = {}
    regex = r"^\$\((.*)\)$"

    for key in ("user", "password", "token_name", "token_value"):
        value = clusterconfig.get(key)
        if value is not None:
            result = re.match(regex, value)
            if result:
                value = _execute_command(result.group(1))
            auth[key] = value

    logging.debug("Auth: %s", auth)
    # check for "incompatible" auth options
    if "password" in auth and ("token_name" in auth or "token_value" in auth):
        logging.error("Auth: cannot use both password and token options together.")
        sys.exit(1)
    if "token_name" in auth and "token_value" not in auth:
        logging.error("Auth: token-name requires token-value option.")
        sys.exit(1)

    return auth


def main():
    # Disable urllib3 warnings about invalid certs
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # get cli arguments
    args = _parser()

    if hasattr(args, "columns"):
        if not args.sort_by is None and not args.sort_by in args.columns:
            sys.stderr.write(
                f"error: cannot sort by column '{args.sort_by}' because it's not included in the --columns flag.\n"
            )
            sys.exit(1)
        for key, _value in args.filter:
            if not key in args.columns:
                sys.stderr.write(
                    f"error: cannot filter on the column '{key}' because it's not included in the --columns flag.\n"
                )
                sys.exit(1)

    # configure logging
    logging.basicConfig(encoding="utf-8", level=logging.DEBUG if args.debug else logging.INFO)
    logging.debug("Arguments: %s", args)
    logging.info("Proxmox cluster: %s", args.cluster)

    clusterconfig = set_config(args.cluster)
    auth = run_auth_commands(clusterconfig)
    proxmoxcluster = PVECluster(
        clusterconfig.name, clusterconfig.host, config={"node": clusterconfig.node}, verify_ssl=False, **auth
    )

    args.func(proxmoxcluster, args)


if __name__ == "__main__":
    sys.exit(main())
