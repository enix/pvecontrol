import logging
import time
import sys
import re
import curses
import json
import os
import subprocess

from collections import OrderedDict
from enum import Enum

import yaml

from humanize import naturalsize
from prettytable import PrettyTable, TableStyle


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
    if os.getenv("NO_COLOR"):
        return False

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
        curses.endwin()


def teminal_support_utf_8():
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
        columns = table[0].keys()
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
        json_string = x.get_json_string()
        # json_string = x.get_json_string(sortby=sortby, fields=columns)
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


def print_task(proxmox, upid, follow=False, wait=False):
    task = proxmox.find_task(upid)
    logging.debug("Task: %s", task)
    # Vanished tasks don't have any more information available in the API
    if task.vanished():
        print_taskstatus(task)
        return

    log = task.log(limit=0)
    logging.debug("Task Log: %s", log)

    if task.running():
        if follow:
            print_taskstatus(task)
            lastline = 0
            print("log output, follow mode")
            while task.running():
                task.refresh()
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
        print_output([{"log output": task.decode_log()}])

    print_taskstatus(task)


def defaulter(resource: dict, keys, default):
    for k in keys:
        if k not in resource.keys():
            resource[k] = default
    return resource


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
