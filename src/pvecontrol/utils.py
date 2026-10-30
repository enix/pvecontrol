import logging
import time
import sys
import re
import curses
import json
import subprocess

from collections import OrderedDict
from enum import Enum

import click
import proxmoxer.core
import yaml
from proxmoxer.tools import Tasks

from humanize import naturalsize
from prettytable import PrettyTable, TableStyle
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout


def parse_pve_version(version):
    """Turn a Proxmox VE version string ("9.1", "9.2.4", "9.0~beta1") into a tuple of ints.

    Tuples compare component by component, so (9, 10) > (9, 2) and (10, 0) > (9, 1),
    unlike the float values of the same strings.
    """
    match = re.match(r"\d+(?:\.\d+)*", str(version).strip())
    if match is None:
        raise ValueError(f"Cannot parse Proxmox VE version {version!r}")
    return tuple(int(part) for part in match.group(0).split("."))


class Fonts:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


class OutputFormats(Enum):
    TEXT = "text"
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"
    MARKDOWN = "md"

    def __str__(self):
        return self.value


def terminal_support_colors():
    try:
        _stdscr = curses.initscr()
        curses.start_color()
        if curses.has_colors():
            _num_colors = curses.color_pair(1)
            return curses.COLORS > 0
        return False
    except Exception:  # pylint: disable=broad-exception-caught
        return False
    finally:
        try:
            curses.endwin()
        except Exception:  # pylint: disable=broad-exception-caught
            pass


def terminal_support_utf_8():
    return sys.stdout.encoding.lower() == "utf-8"


NATURALSIZE_KEYS = [
    "mem",
    "allocatedmem",
    "maxmem",
    "disk",
    "allocateddisk",
    "maxdisk",
]


def render_output(table, columns=None, sortby=None, filters=None, output=OutputFormats.TEXT):
    if not columns:
        columns = []
    if not filters:
        filters = []

    if len(columns) == 0:
        columns = list(table[0].keys())
    else:
        table = [reorder_keys(n.__dict__ if hasattr(n, "__dict__") else n, columns) for n in table]

    x = prepare_prettytable(table, sortby, filters)

    if sortby is not None:
        sortby = "sortby"

    if output in (OutputFormats.TEXT, OutputFormats.MARKDOWN):
        if output == OutputFormats.MARKDOWN:
            x.set_style(TableStyle.MARKDOWN)
        return x.get_string(sortby=sortby, fields=columns)
    if output == OutputFormats.CSV:
        return x.get_csv_string(sortby=sortby, fields=columns)
    if output in (OutputFormats.JSON, OutputFormats.YAML):
        json_string = x.get_json_string(sortby=sortby, fields=columns)
        data = json.loads(json_string)[1:]
        if output == OutputFormats.JSON:
            return json.dumps(data)
        return yaml.dump(data)

    return None


def prepare_prettytable(table, sortby, filters):
    do_sort = sortby is not None

    x = PrettyTable()
    x.align = "l"
    x.field_names = [*table[0].keys(), "sortby"] if do_sort else table[0].keys()

    for line in table:
        for key in line:
            if isinstance(line[key], Enum):
                line[key] = str(line[key])
            # transform set to list as some output does not support it
            if isinstance(line[key], set):
                line[key] = list(line[key])

        if do_sort:
            line["sortby"] = line[sortby]
        for key in NATURALSIZE_KEYS:
            if key in line:
                line[key] = naturalsize(line[key], binary=True)

    for filter_key, filter_value in filters:
        re_filter = re.compile(filter_value)
        table = [line for line in table if re_filter.search(str(line[filter_key]))]

    for line in table:
        x.add_row(line.values())

    return x


def print_output(table, columns=None, sortby=None, filters=None, output=OutputFormats.TEXT):
    print(render_output(table, columns, sortby, filters, output))


def reorder_keys(input_d, keys):
    # Reorder keys from input dict
    output = OrderedDict()
    input_keys = input_d.keys()
    output_keys = keys + [item for item in input_keys if item not in keys]
    for key in output_keys:
        output[key] = input_d[key]
    return output


def print_taskstatus(task):
    columns = [
        "upid",
        "exitstatus",
        "node",
        "runningstatus",
        "type",
        "user",
        "starttime",
    ]
    print_output([task], columns)


# The HA manager handles a migration request on its next round, every 10 s
HA_MIGRATION_START_TIMEOUT = 120
HA_MIGRATION_SETTLE_TIMEOUT = 60


def _ha_migration_upid(proxmox, upid):
    """Return the qmigrate task the HA manager runs for a hamigrate request, or None if it doesn't start one"""
    request = Tasks.decode_upid(upid)
    deadline = time.monotonic() + HA_MIGRATION_START_TIMEOUT
    while time.monotonic() < deadline:
        for task in proxmox.api.cluster.tasks.get():
            if (
                task["type"] == "qmigrate"
                and task.get("id") == request["id"]
                and task["starttime"] >= request["starttime"]
            ):
                return task["upid"]
        time.sleep(2)
    return None


def _follow_ha_migration(proxmox, task, follow, wait):
    """A VM managed by HA is not migrated by a hamigrate task: it only asks the HA manager to do it in a task of its own.
    Return the task that actually migrated the VM, the given task otherwise."""
    if task.type != "hamigrate" or task.exitstatus != "OK" or not (follow or wait):
        return task
    ha_upid = _ha_migration_upid(proxmox, task.upid)
    if ha_upid is None:
        logging.error("The HA manager didn't start the migration requested by %s", task.upid)
        sys.exit(1)
    logging.info("Following the migration run by the HA manager: %s", ha_upid)
    ha_task = print_task(proxmox, ha_upid, follow, wait)
    _wait_ha_settled(proxmox, f"vm:{Tasks.decode_upid(task.upid)['id']}")
    return ha_task


def _wait_ha_settled(proxmox, sid):
    """The HA manager records the end of a migration on its next round only, and ignores new requests for the service
    until then: a request to migrate it back would be dropped as 'already on target node'"""
    deadline = time.monotonic() + HA_MIGRATION_SETTLE_TIMEOUT
    while time.monotonic() < deadline:
        services = [entry for entry in proxmox.api.cluster.ha.status.current.get() if entry.get("sid") == sid]
        if not services or services[0].get("state") != "migrate":
            return
        time.sleep(2)
    logging.warning("The HA manager still reports %s as migrating", sid)


def _get_task(proxmox, upid):
    task = proxmox.get_task(upid)
    logging.debug("Task: %s", task)
    if task is None:
        logging.error("Task %s not found", upid)
        sys.exit(1)
    return task


def print_task(proxmox, upid, follow=False, wait=False):
    task = _get_task(proxmox, upid)
    # Vanished tasks don't have any more information available in the API, and the log is read from the node
    if task.vanished() or task.unknown() or not proxmox.is_node_online(task.node):
        print_taskstatus(task)
        if task.unknown() and (follow or wait):
            logging.error("Can't wait for task %s, node %s can't be reached", upid, task.node)
            sys.exit(1)
        return task

    log = task.log(limit=0)
    logging.debug("Task Log: %s", log)

    if task.running():
        if follow:
            print_taskstatus(task)
            lastline = 0
            print("log output, follow mode")
            while task.running():
                task.refresh()
                if task.unknown():
                    break
                # logging.debug("Task status: %s", status)
                log = task.log(limit=0, start=lastline)
                logging.debug("Task Log: %s", log)
                for line in log:
                    print(str(line["t"]))
                    if line["n"] > lastline:
                        lastline = line["n"]
                time.sleep(1)
        elif wait:
            print_taskstatus(task)
            while task.running():
                task.refresh()
                print(".", end="")
                sys.stdout.flush()
                time.sleep(1)
            print("")
    elif not wait:
        print(task.decode_log())

    print_taskstatus(task)
    if task.unknown():
        logging.error("Lost track of task %s, node %s can't be reached anymore", upid, task.node)
        sys.exit(1)
    return _follow_ha_migration(proxmox, task, follow, wait)


def confirm(force=False):
    """Ask the user to confirm before running a destructive action.

    Returns True when the action is confirmed, either interactively or because force is set.
    Returns False when the user declines, the caller is expected to abort.
    """
    if force:
        return True

    confirmation = click.confirm("Confirm")
    logging.debug("Confirmation input: %s", confirmation)
    if not confirmation:
        print("Aborting")
        return False

    return True


# Errors of an API call proxied to a node, the ones node_unreachable() can tell about
NODE_ERRORS = (proxmoxer.core.ResourceException, RequestsConnectionError, Timeout)


def node_unreachable(error):
    """The API answers 595 when it can't reach the node, a network partition can also make the request fail"""
    if isinstance(error, proxmoxer.core.ResourceException):
        return error.status_code == 595
    return isinstance(error, (RequestsConnectionError, Timeout))


def defaulter(resource: dict, keys, default):
    for k in keys:
        if k not in resource.keys():
            resource[k] = default
    return resource


def _execute_command(cmd):
    return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True).stdout.rstrip()


SECRET_KEYS = ["password", "token_value"]


def redact_secrets(value):
    """Return a copy of a configuration value that is safe to log, with its secrets masked"""
    if isinstance(value, dict):
        return {k: "***" if k in SECRET_KEYS and v is not None else redact_secrets(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    return value


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
                try:
                    value = _execute_command(result.group(1))
                except subprocess.CalledProcessError as e:
                    message = f"Auth: the command for {key} failed with exit status {e.returncode}"
                    if e.stderr.strip():
                        message += f": {e.stderr.strip()}"
                    logging.error(message)
                    sys.exit(1)
            auth[key] = value

    if "proxy_certificate" in auth and isinstance(auth["proxy_certificate"], str):
        proxy_certificate = json.loads(auth["proxy_certificate"])
        auth["proxy_certificate"] = {
            "cert": proxy_certificate.get("cert"),
            "key": proxy_certificate.get("key"),
        }

    if "proxy_certificate" in auth:
        auth["cert"] = (auth["proxy_certificate"]["cert"], auth["proxy_certificate"]["key"])
        del auth["proxy_certificate"]

    logging.debug("Auth: %s", redact_secrets(auth))
    # check for "incompatible" auth options
    if "password" in auth and ("token_name" in auth or "token_value" in auth):
        logging.error("Auth: cannot use both password and token options together.")
        sys.exit(1)
    if "token_name" in auth and "token_value" not in auth:
        logging.error("Auth: token-name requires token-value option.")
        sys.exit(1)

    return auth
