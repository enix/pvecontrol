# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`pvecontrol` is a Python CLI tool for managing Proxmox VE clusters. It wraps the [proxmoxer](https://pypi.org/project/proxmoxer/) library to provide higher-level operations not available in the Proxmox web UI (bulk VM listing, node evacuation/migration, sanity checks, cluster reports).

## Development Setup

```shell
# Activate the virtual environment
source .env/bin/activate

# Run the tool
pvecontrol --help
```

To recreate the environment from scratch:

```shell
python3 -m venv .env
.env/bin/pip install -r requirements.txt -r requirements-dev.txt -e .
```

## Commands

```shell
# Run all tests
pytest src/

# Run a single test file
pytest src/tests/test_cluster.py

# Lint
pylint src/pvecontrol/

# Format (line length 120)
black src/
```

## Architecture

The codebase follows a clean separation between CLI, business logic (actions), and domain models.

**Entry point**: `src/pvecontrol/__init__.py` — defines the Click group `pvecontrol`, wires all subcommands, and exports `main()`.
- The group uses a custom `IgnoreRequiredForHelp(click.Group)` class that walks down to the leaf command (`get_leaf_command`) so `--help` works even when required options are missing, and flattens sub-subcommands in the help listing.
- Global options: `-d/--debug`, `-o/--output`, `-c/--cluster`, `--config`, `--unicode/--no-unicode`, `--color/--no-color`. `main()` calls the group with `auto_envvar_prefix="PVECONTROL"`, so `envvar="CLUSTER"` in the code is exposed as `PVECONTROL_CLUSTER`.
- Cluster autodetection: when `-c/--cluster` is omitted, a single configured cluster is selected automatically; zero or several clusters is a fatal error listing what is available.
- Parsed globals land in `ctx.obj["args"]` as a `SimpleNamespace(output, cluster, unicode, color)`.

**CLI decorators**: `src/pvecontrol/cli.py` — reusable Click helpers (`with_table_options`, `task_related_command`, `migration_related_command`, `ResourceGroup`, `add_list_resource_command`) shared across action modules.

**Actions** (`src/pvecontrol/actions/`): One module per resource type (`cluster`, `node`, `vm`, `storage`, `task`, `acl`, `group`, `user`, `report`), all re-exported from `actions/__init__.py`. Each module defines Click commands and calls into models. Actions instantiate `PVECluster.create_from_config(cluster_name)` to get a connected cluster object.
- `report.py` builds a multi-section cluster report (resource overview, HA groups, backup jobs, users/groups/ACLs, VM summary, sanity-check results) and renders it, markdown by default.

**Models** (`src/pvecontrol/models/`): Domain objects wrapping the Proxmox API:
- `PVECluster` — top-level object; holds `nodes`, `storages`, and lazy-loaded `tasks`, `ha`, `backups`, `backup_jobs`, `users`, `groups`, `acls`; created via `create_from_config()`. Also exposes aggregate `cpu_metrics` / `memory_metrics` / `disk_metrics` / `metrics` properties. The `ha` property handles both the pre-9.1 HA groups API and the `cluster/ha/rules` API used from Proxmox 9.1 on.
- `PVENode` — holds a list of `PVEVm` instances; computes `allocatedcpu` / `allocatedmem`
- `PVEVm`, `PVEStorage`, `PVEVolume`, `PVETask`, `PVEBackupJob` — thin wrappers around API data
- `PVEUser`, `PVEGroup`, `PVEAcl` — access-control objects; they validate their input in `__init__` (raising `ValueError`), normalize comma-separated fields into lists, and each module exposes a `COLUMNS` list used by the table output

**Configuration**: `src/pvecontrol/config.py` uses [confuse](https://confuse.readthedocs.io/) to load `~/.config/pvecontrol/config.yaml` on top of the packaged `config_default.yaml`. `configtemplate` is the schema; `list_clusters()` returns configured cluster names and `set_config(cluster_name)` resolves one cluster's config, merging in the global `node` / `vm` defaults.
- `--config PATH` (or `PVECONTROL_CONFIG`) re-reads the config with `read(user=False, defaults=True)` before layering the given file, so the user config is skipped entirely — confuse merges key by key and list entries by index, which would otherwise leak values across clusters.

**Output**: `src/pvecontrol/utils.py` — `print_output()` / `render_output()` render data via `prettytable` in text/json/csv/yaml/md formats. Memory/disk keys in `NATURALSIZE_KEYS` are automatically humanized. `run_auth_commands()` builds the proxmoxer auth kwargs and implements the `$(...)` shell command substitution supported in the `user`, `password`, `token_name`, `token_value` and `proxy_certificate` config fields.

**Sanity checks** (`src/pvecontrol/sanitycheck/`):
- `checks.py` — abstract base `Check` class with `CheckCode` (OK/WARN/INFO/CRIT) and `CheckType` enums
- `tests/` — concrete check implementations: `Nodes`, `HaGroups`, `HaVms`, `VmsStartOnBoot`, `VmBackups`, `DiskUnused`, registered by `id` in the `DEFAULT_CHECKS` dict (`DEFAULT_CHECK_IDS` for the keys) in `tests/__init__.py`
- `sanitychecks.py` — `SanityCheck` orchestrates running checks and displaying results; exits with code 1 on any CRIT

**Tests** (`src/tests/`): Use `unittest` + `responses` for HTTP mocking. Test fixtures live in `src/tests/fixtures/api.py`.
- `src/tests/testcase.py` defines `PVEEmptyClusterTestcase` (mocked auth plus the base `version` / `cluster/status` / `cluster/resources` routes, cluster built with no resources) and `PVEControlTestcase`, which adds fake nodes, VMs, storages and backups.
- Subclass via the hooks rather than overriding `setUp`: `_build_fixtures()` (populate `self.nodes`, `self.vms`, `self.users`, … before the response wrapper is created), `_register_routes()`, `_cluster_config()`, and `_post_setup()` (runs with the response mock still active).

## Conventions

- Commits must follow [Angular Conventional Commits](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-format) — releases are automated via `python-semantic-release`
- Allowed commit tags: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `style`, `refactor`, `test`
- Branch names follow the same convention: `<type>/<short-description>`, where `<type>` is one of the commit tags above and the description is a short kebab-case summary (e.g. `feat/vm-lock`, `fix/backup-listing`, `docs/add-claude-md`, `refactor/tests`)
- All changes must go through a PR with review; `main` is protected
- Line length: 120 (black) / 150 (pylint)
