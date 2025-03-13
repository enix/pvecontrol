import logging
import time
import sys
import re
import curses
import json
import os

from collections import OrderedDict
from enum import Enum
import click

import yaml

from humanize import naturalsize
from prettytable import PrettyTable, TableStyle
from argparse import ArgumentTypeError
 
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

    def __str__(self):
        return self.value


def _make_filter_type_generator(columns):
    def _regexp_type(value):
        try:
            return re.compile(value)
        except re.error as e:
            raise ArgumentTypeError(f"invalid regular expression: '{value}'", e)

    def _column_type(value):
        if not value in columns:
            choices = ", ".join([f"'{c}'" for c in columns])
            raise ArgumentTypeError(f"invalid choice: '{value}' (choose from {choices})")
        return value

    while True:
        yield _column_type
        yield _regexp_type

# this replaces: pvecontrol.add_table_related_arguments(p,c,d)
def add_table_options(columns, default):

    filter_type_generator = _make_filter_type_generator(columns)

    def filter_type(x):
        return next(filter_type_generator)(x)

    def check_cols(cols):
        res = []
        for col in cols.split(','):
            if col in columns:
                res.append(col)
            else:
                logging.warning(f"Column ({col}) doesn't exist, will be ignored...")
        return res

    def _add_options(func):
        func = click.option('--sort-by', type=click.Choice(columns), default=default,
            show_default=True, help='Key used to sort items')(func)
        func = click.option('--columns', type=str, default=','.join(columns),
            show_default=True, help='Comma-separated list of columns',
            callback=lambda *v: check_cols(v[2]))(func)
        func = click.option('--filter', type=filter_type, nargs=2,
            help="Regex to filter items: colum regexp", callback=lambda *v: [] if v[2] is None else [v[2]] )(func)
        return func
    return _add_options


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
        table = [filter_keys(n.__dict__ if hasattr(n, "__dict__") else n, columns) for n in table]

    x = prepare_prettytable(table, sortby, filters)

    if sortby is not None:
        sortby = "sortby"

    if output == OutputFormats.TEXT:
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


def filter_keys(input_d, keys):
    # Filter keys from input dict
    output = OrderedDict()
    for key in keys:
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
