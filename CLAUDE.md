# CLAUDE.md

Guidance for AI coding agents (Claude Code, and any tool reading `AGENTS.md`) working in this repository.

## Project Overview

`pvecontrol` is a Python CLI that manages Proxmox VE clusters through the HTTP API only, via [proxmoxer](https://pypi.org/project/proxmoxer/). It exists for teams operating several clusters with many hypervisors and covers what the web UI and `qm`/`pvesh` make tedious:

- **Inventory** across all nodes: `vm`, `node`, `storage`, `task`, `user`, `group`, `acl` each have a `list` subcommand with sorting, regex filters and 5 output formats (`text`, `json`, `csv`, `yaml`, `md`).
- **Operations**: `vm migrate`, `vm restore`, `node evacuate` (drain a node, picking targets that respect the `cpufactor` overcommit ratio and the `memoryminimum` host reserve), `task get` with `--follow` / `--wait`.
- **Audit**: `sanitycheck` (6 checks, exit code 1 on any CRITICAL) and `report` (a Markdown cluster report that aggregates everything, including the sanity checks).

Published on PyPI, released automatically by python-semantic-release from `main`.

### Scope and support policy

- **Qemu VMs only.** LXC containers are deliberately ignored everywhere (only `type == "qemu"` resources are read, including for capacity computations). This is a known, accepted limitation. Do not add LXC support unless asked.
- **Only Proxmox VE versions still supported upstream** are targeted (see <https://endoflife.date/proxmox-ve>). Code for EOL versions may keep working but is not maintained: do not add compatibility shims for them. Today that means 9.x is the primary target; the PVE 8 code paths (for example the pre-9.1 `cluster/ha/groups` API) are legacy.


## Development setup

The team works from a virtualenv named `.env` at the root of the main checkout:

```shell
python3 -m venv .env
source .env/bin/activate
pip install -r requirements.txt -r requirements-dev.txt -e .
```

`requirements.lock.txt` / `requirements-dev.lock.txt` pin the whole closure to exact versions, for a reproducible install and for GitHub's dependency graph (Dependabot). Regenerate them with `pip-compile --strip-extras --output-file=requirements.lock.txt requirements.txt` after touching the matching `requirements*.txt`. The dev lock needs Python >= 3.10, so CI keeps installing the unpinned files.

Python 3.9 to 3.13 are supported (CI matrix). In a **git worktree**, the `-e .` install still points at the main checkout's `src/`, so run tests with `PYTHONPATH=src` or reinstall in editable mode from the worktree.

```shell
pytest                 # whole suite, ~1 s, HTTP is mocked (no cluster needed)
pytest src/tests/test_cluster.py
black . --check --diff # line length 120
pylint src/            # max line length 150, see disabled checks in pyproject.toml
```

CI runs black, pylint and pytest on every PR. All three must pass. Never test against a production cluster; there is no Proxmox instance in CI.

## Architecture

Four layers, top to bottom. Each command builds a `PVECluster` from the config, then works on model objects.

**1. CLI entry point**: `src/pvecontrol/__init__.py`
- `pvecontrol` is a Click group with the custom class `IgnoreRequiredForHelp`. It walks down to the leaf command (`get_leaf_command`) so `--help` works without `--cluster`, and flattens `node list`, `vm migrate`, etc. into a single "Commands" listing.
- Global options: `-d/--debug`, `-o/--output`, `-c/--cluster`, `--config`, `--unicode/--no-unicode`, `--color/--no-color`. `main()` sets `auto_envvar_prefix="PVECONTROL"`, so `envvar="CLUSTER"` in the code means `PVECONTROL_CLUSTER` for users.
- Cluster autodetection: without `-c`, exactly 1 configured cluster is picked automatically; 0 or several is a fatal error.
- Parsed globals land in `ctx.obj["args"]` (a `SimpleNamespace` with `output`, `cluster`, `unicode`, `color`). Subcommands read them from there.

**2. Actions**: `src/pvecontrol/actions/`, 1 module per resource, re-exported by `actions/__init__.py`.
- Read-only resources (`acl`, `group`, `user`, `storage`, `task`) are 15-line modules: a `click.group` with `cls=ResourceGroup` from `cli.py`, which auto-generates the `list` subcommand from a `COLUMNS` list, a default sort key and a callback returning the objects.
- `cli.py` also holds the shared option decorators: `with_table_options` (`--columns`, `--filter COL REGEX`, `--sort-by`), `task_related_command` (`-f/--follow`, `-w/--wait`), `migration_related_command` (adds `--online`, `--dry-run`).
- `report.py` is the largest action: `_build_report_data()` gathers plain dicts, `_render_report()` turns them into Markdown sections. Keep that split when adding a section.

**3. Models**: `src/pvecontrol/models/`, thin wrappers over API dicts.
- `PVECluster` is the root. `__init__` calls `version`, `cluster/status`, `cluster/resources`, then builds one `PVENode` per node resource (each node fetches its own `nodes/{node}/version`) and the `PVEStorage` list. Everything else (`ha`, `tasks`, `backups`, `backup_jobs`, `users`, `groups`, `acls`) is a lazy property cached in a `_xxx = None` attribute. `refresh()` rebuilds status, tasks and HA.
- `PVECluster.create_from_config(name)` is the only place that reads config and authenticates. Actions call it once at the start.
- `PVENode` builds its `PVEVm` list from `cluster/resources` (only when the node is ONLINE) and computes `allocatedcpu` / `allocatedmem` from **running** VMs only. `node evacuate` mutates these counters while planning placements.
- `PVEVm.config` lazily fetches `qemu/{vmid}/config` (1 API call per VM, cached on the object). Sanity checks rely on it heavily.
- `PVEStorage`: 1 object per (node, storage) pair as returned by `cluster/resources`. `get_grouped_list()` merges shared storages by name; `get_flattened_grouped_list()` mutates the underlying objects (see Gotchas).
- `PVETask` decodes the UPID locally and fetches status; a task whose status file vanished on the node is `VANISHED`, not an error.
- `PVEUser`, `PVEGroup`, `PVEAcl` validate in `__init__` (`ValueError`) and normalize comma-separated API fields into lists. Each model module exposes a `COLUMNS` list consumed by the `list` command.
- The `ha` property handles both APIs: `cluster/ha/rules` on PVE >= 9.1, `cluster/ha/groups` before.

**4. Config and output**
- `config.py` uses [confuse](https://confuse.readthedocs.io/): the packaged `config_default.yaml` is the base, `~/.config/pvecontrol/config.yaml` is layered on top. `configtemplate` is the schema. `list_clusters()` and `set_config(name)` (case-insensitive match, merges global `node:` / `vm:` defaults into the cluster) are the 2 entry points.
- `utils.py`: `render_output()` / `print_output()` build a `prettytable` and emit the requested format. Keys listed in `NATURALSIZE_KEYS` are humanized automatically. `run_auth_commands()` turns a cluster config into proxmoxer kwargs and implements the `$(command)` substitution for `user`, `password`, `token_name`, `token_value` and `proxy_certificate`. `print_task()` implements `--follow` / `--wait`.

**Sanity checks**: `src/pvecontrol/sanitycheck/`
- `checks.py`: abstract `Check` (class attributes `id`, `type`, `name`; implement `run()` and call `self.add_messages(CheckMessage(CheckCode.X, text))`). A check's status is its worst message; `CRIT` anywhere makes the command exit 1.
- `tests/`: 1 module per theme, registered by `id` in `DEFAULT_CHECKS` in `tests/__init__.py`. Adding a check means: subclass `Check`, set the 3 class attributes, add it to that dict. It then appears in `sanitycheck` argument completion and in `report`.
- `sanitychecks.py`: `SanityCheck` runs the selected checks and renders them grouped by `CheckType`.

## Tests

`src/tests/`, pytest with `unittest.TestCase` classes and the `responses` library. No network, no cluster.

- Fixtures in `src/tests/fixtures/api.py` fake the Proxmox API (`fake_node`, `fake_vm`, `fake_storage_resource`, `fake_backup_job`, `fake_ha_rule`, `fake_user`, ...) and build a route table with `generate_routes()`. They simulate PVE 9.1.4.
- `src/tests/testcase.py`: `PVEEmptyClusterTestcase` (auth mocked, base routes only) and `PVEControlTestcase` (3 nodes, 5 VMs, an `s3` storage, backups). Extend them through the hooks, never by overriding `setUp`: `_build_fixtures()` to set `self.nodes`, `self.vms`, `self.users`, ... before the route table is built; `_register_routes()` for extra routes; `_cluster_config()` for `cpufactor` / `memoryminimum` / `max_last_backup`; `_post_setup()` runs once `self.cluster` exists, with the response mock still active.
- Older tests (`sanitycheck/test_vm_disks.py`) patch `ProxmoxHttpSession.request` directly with `mock_api_requests()`. Prefer the `responses`-based test case for new tests.
- Pure model tests (`test_user.py`, `test_group.py`, `test_acl.py`, `test_backup_job.py`) need no cluster.

## Conventions

- **Commits** follow the Angular convention (`type(scope): subject`) because releases and the CHANGELOG are generated from them. Allowed types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `style`, `refactor`, `test`. `feat` bumps minor, `fix` / `perf` bump patch.
- **Branches**: `<type>/<kebab-description>` with the same types (`feat/vm-lock`, `docs/claude-md`).
- `main` is protected: every change goes through a PR with a review. Releases are triggered manually from `main` via the "Release New version" workflow.
- Code, comments, docstrings, commit messages and docs are in English.
- Formatting is black (120 columns). Pylint runs with the exceptions listed in `pyproject.toml`; do not add new `# pylint: disable` comments without a reason, and remove the `FIXME`-tagged ones when you touch that code.
- User-facing errors: existing code mixes `print()` + `sys.exit(1)` and `logging.error()`. Prefer `logging` (goes to stderr, keeps `-o json` output clean) and a non-zero exit code.

## Gotchas

- **confuse merges lists by index.** That is why `--config` calls `config.read(user=False, defaults=True)` before `set_file()`: layering a second file on the user config would merge cluster entries positionally. Keep that behavior.
- **`node evacuate` only migrates running VMs by default** (`--no-skip-stopped` to include stopped ones) and `--online` defaults to false. Placement is greedy, in VM order, against the mutable `allocatedmem` / `allocatedcpu` of each target.
- **`PVEStorage.get_flattened_grouped_list()` mutates the `PVEStorage` objects** (it pops `node` from their `__dict__`). `report.py` runs the sanity checks before the storage section for that reason. Do not call it before code that still needs intact storage objects.
- **`PVECluster.tasks` costs 1 API call per task** returned by `cluster/tasks`. `refresh()` re-fetches them all.
- **Offline nodes**: `PVENode.__init__` fetches the node version unconditionally. Behavior with an offline node is untested.
- `terminal_support_colors()` calls `curses.initscr()`; it is invoked for every rendered sanity-check message.
- Proxmox returns kebab-case keys in places (`realm-type`, `next-run`, `prune-backups`). Map them explicitly when a model attribute uses snake_case.
- Do not read `~/.config/pvecontrol/config.yaml` or any file that may hold credentials; ask the user for its structure instead.

