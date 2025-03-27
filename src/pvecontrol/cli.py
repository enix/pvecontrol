import click
import re
import logging

from argparse import ArgumentTypeError


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


def with_table_options(columns, default_sort):
    filter_type_generator = _make_filter_type_generator(columns)

    def filter_type(x):
        return next(filter_type_generator)(x)

    def check_cols(cols):
        res = []
        for col in cols.split(","):
            if col in columns:
                res.append(col)
            else:
                logging.warning(f"Column ({col}) doesn't exist, will be ignored...")
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
        func = click.option(
            "--filter",
            type=filter_type,
            nargs=2,
            metavar="COLUMN REGEXP",
            help="Regex to filter items",
            callback=lambda *v: [] if v[2] is None else [v[2]],
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
    func = click.option("-w", "--wait", is_flag=True, help="Follow task log output")(func)
    func = click.option("-f", "--follow", is_flag=True, help="Wait task end")(func)
    return func


def migration_related_command(func):
    func = click.option("--dry-run", is_flag=True, help="Dry run, do not execute migration for real")(func)
    func = click.option("--online", is_flag=True, default=True, help="Perform anonline migration")(func)
    func = task_related_command(func)
    return func
