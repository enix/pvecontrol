# Node HA maintenance: study and implementation plan

## Context

Goal: put a node in maintenance through the HA manager from pvecontrol, and show each node's HA state in `node list`.

### What Proxmox actually exposes (checked on 2026-10-28)

- **No released PVE version has an HTTP endpoint to enable or disable node maintenance.** A search for `maintenance` in the full API schema (`pve-docs/api-viewer/apidata.js` at HEAD), in `pve-manager/PVE/API2/Nodes.pm` and in `pve-ha-manager/src/PVE/API2/HA/*` finds nothing. Only the CLI command `ha-manager crm-command node-maintenance enable|disable <node>` does it, by writing to `/etc/pve/ha/crm_commands`.
- Two patch series proposed such an endpoint: `POST /cluster/ha/nodes/{node}/maintenance` (August 2025), then `PUT /nodes/{node}/maintenance --maintenance-mode enable|disable` (v3, October 2025, bug #6144). **Neither was applied.** On 2026-03-24, Proxmox said it plans a dedicated endpoint that also covers non-HA resources, and will revisit the series later.
- **Reading the state works** through `GET /cluster/ha/status/manager_status` (needs `Sys.Audit` on `/`), which `PVECluster.ha` already calls:
  - `manager_status.node_status[node]` is `online`, `maintenance`, `unknown`, `fence` or `gone`.
  - `manager_status.node_request[node].maintenance == 1` means maintenance was requested but may not be effective yet.
  - `lrm_status[node].mode` is `active`, `maintenance`, `restart`, `shutdown` or `disarm`.
  - `manager_status.disarm = {mode, state}` is present when HA is disarmed.
- **Writable today**: `POST /cluster/ha/status/disarm-ha` (`resource-mode=freeze|ignore`) and `POST /cluster/ha/status/arm-ha`, both needing `Sys.Console`. They landed in pve-ha-manager 5.1.3 (PVE 9.1). Their presence can be detected through the `GET /cluster/ha/status` index.

Sources:

- [Patch series v3, bug #6144](https://lore.proxmox.com/all/DHB215RUKG6G.FG3V76HOMAYV@proxmox.com/t)
- [Patch, August 2025](https://lists.proxmox.com/pipermail/pve-devel/2025-August/074710.html)
- pve-ha-manager: `src/PVE/HA/Manager.pm`, `src/PVE/HA/NodeStatus.pm`, `src/PVE/API2/HA/Status.pm`

## Decisions

- **No `node maintenance enable|disable` for now**: wait for the upstream endpoint. No SSH, no simulated maintenance.
- Features in scope:
  - HA state column in `node list`;
  - `node evacuate` skips targets in maintenance;
  - HA nodes sanity check;
  - `node maintenance status --wait`;
  - `cluster ha arm|disarm`.
- No dedicated HA section in `report`: the sanity check shows up there automatically.

## Plan

### Phase 1: HA state in `node list`

- `src/pvecontrol/models/cluster.py`: add a lazy `ha_manager_status` property that makes a single call (`cluster/ha/status/manager_status`).
  - Cached in `_ha_manager_status` and reset by `refresh()`.
  - If the call fails (no `Sys.Audit`, `ResourceException`), it returns `{}` and logs at debug level.
  - `ha` reuses this property instead of making the call again.
- `src/pvecontrol/models/node.py`:
  - Add a `NodeHaState` enum: `NONE`, `ONLINE`, `MAINTENANCE_REQUESTED`, `MAINTENANCE`, `UNKNOWN`, `FENCE`, `GONE`.
  - Add an `ha_state` property computed from `node_status`, `node_request` and `lrm_status.mode`.
  - Tell three cases apart: maintenance requested (`node_request` set while `node_status` is still `online`), maintenance draining (`maintenance` with HA services still on the node), and maintenance effective.
  - Add `ha_state` to `COLUMNS`. The column shows `-` when the cluster has no HA or the permission is missing.
- `src/pvecontrol/cli.py` (`add_list_resource_command`): replace `item.__dict__[k]` with `getattr(item, k)` for objects. Without it, a `@property` raises `KeyError`. The other `list` commands (acl, user, ...) are unaffected.
- Tests:
  - `src/tests/fixtures/api.py`: the current fixture returns `[]`, but the real response is an object. Add a realistic `fake_ha_manager_status(node_status=..., node_request=..., lrm_modes=...)`.
  - New tests for `ha_state` (each state, no HA, 403) and for the column in `node list`. Check that `test_report.py` still passes.

### Phase 2: related features, all doable through the API

1. **`node evacuate` skips HA-unavailable targets**: nodes in maintenance (requested or effective), or in `fence`, `unknown` or `gone` state, are excluded both in automatic selection and as explicit targets, with a message. Today, evacuate can migrate VMs to a node in maintenance.
2. **`ha_nodes` sanity check** (`src/pvecontrol/sanitycheck/tests/ha.py`, registered in `DEFAULT_CHECKS`):
   - WARN for a node in maintenance or a disarmed HA;
   - CRIT for a node in `fence` or `unknown`.
   - The check appears in `report` automatically.
3. **`node maintenance status [NODE] [--wait]`** (`maintenance` click subgroup in `actions/node.py`):
   - shows the node's HA state and the HA services still on it (`manager_status.service_status[sid].node`);
   - `--wait` calls `refresh()` every few seconds until the state is `maintenance` and no HA service is left on the node;
   - without NODE, shows every node;
   - if the node is neither requested nor in maintenance, `--wait` fails with a non-zero exit code and prints the `ha-manager crm-command node-maintenance enable <node>` command to run.
4. **`cluster ha disarm --mode freeze|ignore` / `cluster ha arm`** (`actions/cluster.py`):
   - disarms or re-arms HA fencing through `POST cluster/ha/status/disarm-ha|arm-ha`;
   - before the call, checks that the `GET cluster/ha/status` index exposes `disarm-ha`; otherwise, a clear error (PVE version too old);
   - asks for confirmation with `confirm()` and offers `--wait` to wait until `manager_status.disarm.state` reaches `disarmed`.

Later: once Proxmox publishes the maintenance endpoint, add `node maintenance enable|disable` to the same subgroup, with endpoint detection.

## Pull requests (one branch per phase)

1. `feat/node-ha-state`: phase 1.
2. `fix/evacuate-skip-ha-maintenance`: evacuate (a `fix`, so a patch bump).
3. `feat/sanitycheck-ha-nodes`.
4. `feat/node-maintenance-status`: `node maintenance status --wait`.
5. `feat/cluster-ha-arm-disarm`.

Each PR updates the README for its new commands or columns.

## Verification

- `pytest`, `black . --check --diff`, `pylint src/`.
- Run `pvecontrol -c <test cluster> node list` against a test cluster (never production). Put a node in maintenance with `ha-manager crm-command node-maintenance enable` and check the `maintenance-requested` → `maintenance` transition in the column, and that `node evacuate --dry-run` excludes the node.
- Check the exact shape of `manager_status` on a real cluster (that `node_request` and `disarm` are in the API response) before freezing the fixture. These fields were read from the pve-ha-manager source, not observed on a cluster.
