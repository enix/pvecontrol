# Node HA maintenance: study and implementation plan

Revised on 2026-11-20, after rebasing on `main` (0.9.0) and checking upstream again. The first version of this study
(2026-10-28) concluded that no API could set the maintenance mode; that is no longer true.

## Context

Goal: put a node in HA maintenance from pvecontrol, and show each node's HA state in `node list`.

## What Proxmox exposes

### Setting the maintenance mode: new API, very recent

- **`PUT /nodes/{node}/maintenance`**, parameter `maintenance-mode=enable|disable`, returns `null`, needs `Sys.Modify`
  on `/`. Added by pve-manager **9.2.33** (2026-11-19, "fix #6144"), which depends on pve-ha-manager >= 5.2.7.
  - The call is proxied to `{node}`, which runs `ha-manager crm-command node-maintenance <mode> <node>` locally. The
    node must be online and reachable, and run pve-manager >= 9.2.33.
  - It only queues a request: the CRM handles it on its next round (about 10 s), then the HA manager migrates the HA
    resources away. "Currently, this only requests the HA node maintenance mode": VMs not managed by HA stay on the
    node.
  - Since pve-ha-manager 5.2.7, the request is rejected with a reason (HTTP error) when the CRM would ignore it: HA
    disarmed, node not online, node not tracked by HA. Requesting it again for a node already requested succeeds.
  - pve-manager 9.2.33 is a day old: it may not be in the no-subscription repository yet. Most clusters will not have
    it for a while, so pvecontrol must detect it, not assume it.
- Before 9.2.33, the only way is the CLI `ha-manager crm-command node-maintenance enable|disable <node>` on a node.

### Reading the state: available on every supported version

- `GET /cluster/ha/status/manager_status` (needs `Sys.Audit` on `/`), already fetched by `PVECluster.ha` and
  `PVECluster.ha_imbalance`:
  - `manager_status.node_status[node]`: `online`, `maintenance`, `unknown`, `fence` or `gone`.
  - `manager_status.node_request[node].maintenance == 1`: maintenance requested, possibly not effective yet.
  - `lrm_status[node].mode`: `active`, `maintenance`, `restart`, `shutdown` or `disarm`.
  - `manager_status.service_status[sid].node`: where each HA resource is.
  - `manager_status.disarm = {mode, state}`: present while HA is disarmed.
- `GET /cluster/ha/status/current`, `lrm` entries (pve-ha-manager >= 5.2.7): `maintenance-requested` and
  `maintenance-request-queued` (request written but not yet read by the CRM). Already used by `_wait_ha_settled()` in
  `utils.py`.
- None of these calls reaches the node itself: the HA state of an offline node can be read safely.

### Disarming HA

`POST /cluster/ha/status/disarm-ha` (`resource-mode=freeze|ignore`) and `POST /cluster/ha/status/arm-ha`, with
`Sys.Console`, since pve-ha-manager 5.1.3 (PVE 9.1). Detected through the `GET /cluster/ha/status` index. Enabling the
maintenance mode is refused while HA is disarmed.

Sources:

- pve-manager `PVE/API2/Nodes.pm` (`maintenance_set`) and `debian/changelog` 9.2.33
- pve-ha-manager `src/PVE/API2/HA/Status.pm`, `src/PVE/HA/Manager.pm`, `src/PVE/HA/NodeStatus.pm`,
  `debian/changelog` 5.2.7
- [Patch series v3, bug #6144](https://lore.proxmox.com/all/DHB215RUKG6G.FG3V76HOMAYV@proxmox.com/t)

## What changed in pvecontrol since the first study

- **Models are dataclasses** (`PVENodeData` + `PVENode`, `from_api()`), and list columns are read through
  `utils.column_value()` (`getattr()`): a computed `ha_state` property works as a column with no change to `cli.py`.
  The first plan's `cli.py` step is dropped.
- **`PVECluster.ha_imbalance`** (CRS) already reads `manager_status`, reusing `self._ha` when set, else fetching that
  endpoint alone. `test_ha_crs.py` asserts a single `manager_status` call per run.
- **`fake_ha_manager_status(imbalance)`** exists in `src/tests/fixtures/api.py`, with an empty `node_status`. The
  default route still returns `[]` when no status is given.
- **Offline nodes**: `PVENode` handles unreachable nodes as `UNKNOWN`, and every `nodes/{node}/...` call must be guarded
  with `PVECluster.is_node_online()`. This applies to the new `PUT /nodes/{node}/maintenance`.
- **HA migrations**: `print_task()` follows the `qmigrate` started by the HA manager for a `hamigrate`, and
  `_wait_ha_settled()` polls `cluster/ha/status/current`. The waiting pattern for maintenance can follow it.
- **Errors**: `logging.error()` and exit 1, `ResourceException` caught around API calls, declining a confirmation exits 1
  (`confirm(force)`).
- `node evacuate` still picks any online node as target, including one in HA maintenance.
- Sanity checks: 7 today (`nodes`, `ha_groups`, `ha_vms`, `crs`, `vm`, `vm_backups`, `disk_unused`).

## Decisions

- Kept from the first study: HA state column in `node list`, `node evacuate` skips targets in maintenance, HA nodes
  sanity check, a maintenance status command with `--wait`, HA arm/disarm.
- **Changed**: the first study deferred enabling and disabling the maintenance mode until upstream shipped an endpoint.
  It has shipped, so it moves into scope, through the API only, gated on the node's pve-manager version.
- **Commands stop at 2 levels**, like the existing ones (`node evacuate`, `crs set`, top-level `status`). Maintenance
  and arm/disarm live in a new top-level `ha` group, next to `crs`: no `node maintenance` or `cluster ha` subgroup.

## Commands

```
pvecontrol ha status [NODE] [--wait]
pvecontrol ha maintenance-enable NODE [--wait] [--force]
pvecontrol ha maintenance-disable NODE [--wait] [--force]
pvecontrol ha arm [--wait] [--force]
pvecontrol ha disarm --mode freeze|ignore [--wait] [--force]
pvecontrol node list            # new ha_state column
```

## Plan

### Phase 1: HA state in `node list`

- `src/pvecontrol/models/cluster.py`: add a lazy `ha_manager_status` property, cached in `_ha_manager_status`, that
  fetches `cluster/ha/status/manager_status` once. `ha` and `ha_imbalance` use it instead of their own calls; `refresh()`
  resets it. The single-call assertion of `test_ha_crs.py` must still hold.
- `src/pvecontrol/models/node.py`:
  - `NodeHaState` enum, rendered lowercase like `NodeStatus` (`__str__`): `NONE` (rendered `-`, no HA or no access),
    `ONLINE`, `MAINTENANCE_REQUESTED`, `MAINTENANCE`, `UNKNOWN`, `FENCE`, `GONE`.
  - `ha_state` property from `node_status`, `node_request` and `lrm_status.mode`: requested is `node_request` set while
    `node_status` is still `online`.
  - Add `ha_state` to `COLUMNS`.
  - A `ResourceException` (no `Sys.Audit`) gives `NONE` for every node, with a single warning, not one per node.
- Tests: extend `fake_ha_manager_status()` with `node_status`, `node_request`, `lrm_status` arguments; cover each state,
  no HA, the 403 case and an offline node (no call to the node, see `test_offline_node.py`).
- README: the column in [Listing resources](../README.md#listing-resources).

### Phase 2: `node evacuate` skips HA-unavailable targets

Exclude targets whose `ha_state` is `maintenance_requested`, `maintenance`, `unknown`, `fence` or `gone`, in automatic
selection and for explicit targets, with a warning like the existing "is not online" one. Today evacuate can move VMs
onto a node being drained. Commit type `fix`. README: the Targets bullet of `node evacuate`.

### Phase 3: `ha_nodes` sanity check

`src/pvecontrol/sanitycheck/tests/ha_nodes.py`, `CheckType.HA`, registered in `DEFAULT_CHECKS` next to the other HA
checks (the dict order is the display order):

- WARN: node in maintenance or with maintenance requested, HA disarmed or disarming.
- CRIT: node in `fence` or `unknown`. `gone` is WARN (node removed from the cluster).
- WARN when `manager_status` can't be read, like `HaCrs` does.
- OK otherwise. It shows up in `report` automatically. README: the check list and the count (8 checks).

### Phase 4: `ha` group: `ha status`, `ha maintenance-enable`, `ha maintenance-disable`

New module `src/pvecontrol/actions/ha.py`: a plain `click.group(name="ha", help=...)` like `actions/crs.py`,
re-exported in `actions/__init__.py` and registered in `src/pvecontrol/__init__.py` next to `crs`
(`pvecontrol.add_command(cmd=actions.ha.root, name="ha")`).

- **`ha status [NODE]`**: the armed/disarmed state, then per node: the HA state, whether a request is queued (`current`
  entries when the field exists), the HA resources still on the node (`service_status[sid].node`) and the VMs not
  managed by HA on it. Without NODE, every node.
- **`ha maintenance-enable NODE` / `ha maintenance-disable NODE`**:
  - Checks, each failing with `logging.error()` and exit 1: the node exists, it is online (`is_node_online()`), its
    `version["version"]` is >= 9.2.33 (`parse_pve_version()`, the node version is already fetched by `PVENode`).
    Below that version, the error gives the `ha-manager crm-command node-maintenance <mode> <node>` command to run.
  - Asks for confirmation (`--force` to skip, as in `crs set`), then `PUT nodes/{node}/maintenance`. A
    `ResourceException` is reported with its message (the CRM's reason since 5.2.7) and a note that `Sys.Modify` on
    `/` is needed.
  - `enable` lists the VMs not managed by HA that stay on the node, and points to `node evacuate`.
  - `--wait`: poll with `refresh()` until the target state is reached. For `enable`, `node_status` is `maintenance`
    and no HA resource is left on the node; for `disable`, `node_status` is `online`. Bounded by a `--timeout`, exit 1
    when it expires.
- **`ha status NODE --wait`** waits until the node's pending maintenance request reaches its target state. On a node
  with nothing pending, it exits 1 instead of waiting forever.

### Phase 5: `ha arm` / `ha disarm --mode freeze|ignore`

In the same `actions/ha.py` module.

Checks that the `GET cluster/ha/status` index lists `disarm-ha`, else a clear error. Confirmation (`--force`), then
`POST cluster/ha/status/disarm-ha|arm-ha`. `--wait` until `manager_status.disarm.state` is `disarmed` (or gone for
`arm`). Warns that no node can enter maintenance while HA is disarmed.

## Pull request

A single PR, `feat/node-ha-maintenance`, with one commit per phase so that the changelog lists each change:

1. `feat(node)`: phase 1.
2. `fix(node)`: phase 2.
3. `feat(sanitycheck)`: phase 3.
4. `feat(ha)`: phases 4 and 5.

Each commit updates the README (a new `### ha` section after `### crs` for the `ha` group) and `AGENTS.md`.

## Verification

- `pytest`, `black . --check --diff`, `pylint src/` on each PR.
- Live tests on `enix-devel-1` only, never on another cluster:
  - `node list`: put a node in maintenance with `ha-manager crm-command node-maintenance enable` and follow the
    `maintenance_requested` → `maintenance` → `online` transitions.
  - `node evacuate --dry-run` excludes that node.
  - Record the real `manager_status` payload (`node_request`, `lrm_status`, `disarm`) and the `current` lrm entries,
    and build the fixtures from it. These fields were read from the pve-ha-manager source, not observed on a cluster.
  - Phase 4 needs `enix-devel-1` on pve-manager >= 9.2.33 for `enable` / `disable`; on an older version, check the
    error message instead.
