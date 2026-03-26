# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`pvecontrol` is a Python CLI tool for managing Proxmox VE clusters. It wraps the [proxmoxer](https://pypi.org/project/proxmoxer/) library to provide higher-level operations not available in the Proxmox web UI (bulk VM listing, node evacuation/migration, sanity checks).

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

**CLI decorators**: `src/pvecontrol/cli.py` — reusable Click decorators (`with_table_options`, `task_related_command`, `migration_related_command`, `ResourceGroup`) shared across action modules.

**Actions** (`src/pvecontrol/actions/`): One module per resource type (`cluster`, `node`, `vm`, `storage`, `task`). Each module defines Click commands and calls into models. Actions instantiate `PVECluster.create_from_config(cluster_name)` to get a connected cluster object.

**Models** (`src/pvecontrol/models/`): Domain objects wrapping the Proxmox API:
- `PVECluster` — top-level object; holds `nodes`, `storages`, lazy-loaded `tasks`, `ha`, `backups`, `backup_jobs`; created via `create_from_config()`
- `PVENode` — holds a list of `PVEVm` instances; computes `allocatedcpu` / `allocatedmem`
- `PVEVm`, `PVEStorage`, `PVEVolume`, `PVETask`, `PVEBackupJob` — thin wrappers around API data

**Configuration**: `src/pvecontrol/config.py` uses [confuse](https://confuse.readthedocs.io/) to load `~/.config/pvecontrol/config.yaml`. Supports `$()` shell command substitution in `user`, `password`, `token_name`, `token_value`, and `proxy_certificate` fields.

**Output**: `src/pvecontrol/utils.py` — `print_output()` / `render_output()` render data via `prettytable` in text/json/csv/yaml/md formats. Memory/disk keys in `NATURALSIZE_KEYS` are automatically humanized.

**Sanity checks** (`src/pvecontrol/sanitycheck/`):
- `checks.py` — abstract base `Check` class with `CheckCode` (OK/WARN/INFO/CRIT) and `CheckType` enums
- `tests/` — concrete check implementations: `Nodes`, `HaGroups`, `HaVms`, `VmsStartOnBoot`, `VmBackups`, `DiskUnused`
- `sanitychecks.py` — `SanityCheck` orchestrates running checks and displaying results; exits with code 1 on any CRIT

**Tests** (`src/tests/`): Use `unittest` + `responses` for HTTP mocking. `PVEControlTestcase` in `testcase.py` provides a pre-wired cluster fixture with fake nodes, VMs, backups. Test fixtures live in `src/tests/fixtures/api.py`.

## Conventions

- Commits must follow [Angular Conventional Commits](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-format) — releases are automated via `python-semantic-release`
- Allowed commit tags: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `style`, `refactor`, `test`
- All changes must go through a PR with review; `main` is protected
- Line length: 120 (black) / 150 (pylint)
