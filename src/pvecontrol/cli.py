import re
import logging
import click

from pvecontrol.utils import column_value, print_output
from pvecontrol.models.cluster import PVECluster


class RegexpType(click.ParamType):
    name = "regexp"

    def convert(self, value, param, ctx):
        if isinstance(value, re.Pattern):
            return value
        try:
            return re.compile(value)
        except re.error as e:
            self.fail(f"invalid regular expression: '{value}' ({e})", param, ctx)


def filter_option(columns, *param_decls, help_text):
    """A repeatable option taking a column name and a regular expression"""
    return click.option(
        *param_decls,
        type=(click.Choice(columns), RegexpType()),
        metavar="COLUMN REGEXP",
        multiple=True,
        help=help_text,
    )


def with_table_options(columns, default_sort):
    def check_cols(cols):
        res = []
        for col in cols.split(","):
            if col in columns:
                res.append(col)
            else:
                logging.warning("Column (%s) doesn't exist, will be ignored...", col)
        return res

    def _add_options(func):
        func = click.option(
            "--columns",
            type=str,
            metavar="COLUMNS",
            default=",".join(columns),
            help="Comma-separated list of columns",
            callback=lambda *v: check_cols(v[2]),
        )(func)
        func = filter_option(
            columns, "--filter", "filters", help_text="Regex to filter items (can be set multiple times)"
        )(func)
        func = click.option(
            "--sort-by",
            type=click.Choice(columns),
            default=default_sort,
            show_default=True,
            help="Key used to sort items",
        )(func)
        return func

    return _add_options


def task_related_command(func):
    func = click.option("-w", "--wait", is_flag=True, help="Wait task end")(func)
    func = click.option("-f", "--follow", is_flag=True, help="Follow task log output")(func)
    return func


def migration_related_command(func):
    func = click.option("--dry-run", is_flag=True, help="Dry run, do not execute migration for real")(func)
    func = click.option("--online", is_flag=True, default=False, help="Perform an online migration")(func)
    func = task_related_command(func)
    return func


class ResourceGroup(click.Group):
    def __init__(self, name, columns, default_sort, list_callback, *args, **kwargs):
        kwargs["help"] = f"{name[0].upper()+name[1:]} related commands"
        super().__init__(*args, **kwargs)
        add_list_resource_command(name, self, columns, default_sort, list_callback)


def add_list_resource_command(
    resource_name, root_cmd, default_columns, default_sort, list_callback, command_name="list"
):
    @root_cmd.command(command_name, help=f"List {resource_name}s in the cluster")
    @with_table_options(default_columns, default_sort)
    @click.pass_context
    def _(ctx, sort_by, columns, filters):
        proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
        output = ctx.obj["args"].output

        data = list_callback(proxmox)
        data = [{key: column_value(item, key) for key in default_columns} for item in data]

        print_output(data, columns=columns, sortby=sort_by, filters=filters, output=output)
