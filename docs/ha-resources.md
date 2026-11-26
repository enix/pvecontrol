# HA resources and affinity rules: study and implementation plan

Written on 2026-11-21, on top of the node HA maintenance work (`docs/node-ha-maintenance.md`), in the same PR.

## Context

Goal: manage the HA resources from pvecontrol (add a VM to HA, set its HA parameters, remove it), then the HA rules:
node affinity and resource affinity (affinity and anti-affinity between VMs).

Today pvecontrol only reads them: `PVECluster.ha` fetches `cluster/ha/resources` and `cluster/ha/rules` (or
`cluster/ha/groups` before 9.1), for the `ha_groups`, `ha_vms` and `crs` sanity checks and for `report`.

## What Proxmox exposes

Sources: the API schema (`pve-docs/api-viewer/apidoc.js`), the HA manager chapter of the documentation (9.2.15), and
pve-ha-manager `src/PVE/API2/HA/Rules.pm`, `src/PVE/API2/HA/Resources.pm`, `src/PVE/HA/Rules*.pm`,
`debian/changelog`.

### HA resources

- `GET /cluster/ha/resources` (`Sys.Audit` on `/`): one entry per resource. On enix-devel-1 an entry only holds the
  options that are set (`{"sid": "vm:101", "type": "vm", "state": "started", "digest": ...}`): the defaults must be
  filled by pvecontrol.
- `POST /cluster/ha/resources` (`Sys.Console` on `/`): `sid` (`vm:100`), `state`
  (`started`, `stopped`, `enabled`, `disabled`, `ignored`, default `started`), `max_restart` and `max_relocate`
  (default 1), `failback` (default 1), `auto-rebalance` (default 1, pve-ha-manager 5.2.2), `comment`, `group`
  (refused once the groups are migrated to rules). Refused when the resource exists ("resource ID 'vm:100' already
  defined").
- `PUT /cluster/ha/resources/{sid}`: the same options, plus `delete` (options to reset) and `digest`.
- `DELETE /cluster/ha/resources/{sid}`: `purge` (default 1) also removes the resource from the rules, and deletes the
  rules left with no resource.
- `failback`: when the node with the highest priority of its node affinity rule comes back, the resource moves back to
  it.

### HA rules

Present since pve-ha-manager 5.0.2 (PVE 9.0), the HA groups are migrated to node affinity rules once every node runs
it. Rules can't be written while HA groups remain ("ha groups have not been migrated yet").

- `GET /cluster/ha/rules` (`Sys.Audit`), filters `type` and `resource`. Each entry is the whole rule: `rule`, `type`,
  `resources` and `nodes` as comma-separated strings, `affinity`, `strict`, `disable`, `comment`, `order`, `digest`,
  and **`errors`** (`{option: [message, ...]}`) when the rule fails a feasibility check.
- `POST /cluster/ha/rules` (`Sys.Console`): `rule` (id), `type`, `resources`, `comment`, `disable`, and:
  - `node-affinity`: `nodes` (`node[:priority],...`, the higher the priority the more preferred), `strict` (default 0:
    the listed nodes are preferred, with 1 the resources only run there and stop when none is available), `affinity`
    (`positive` by default, `negative` to keep the resources away from the nodes, pve-ha-manager 5.2.5).
  - `resource-affinity`: `affinity` required, `positive` (keep the resources together) or `negative` (keep them on
    separate nodes, anti-affinity). Always strict.
- `PUT /cluster/ha/rules/{rule}`: the same options, `delete`, `digest`, and `type`, which must match the rule.
- `DELETE /cluster/ha/rules/{rule}`.
- **Validation is done by the API.** On create and update, the resources must be HA resources ("cannot use unmanaged
  resource(s)"), the nodes must exist, then the 9 feasibility checks of the documentation run on the whole rule set
  (one node affinity rule per resource, no priorities in a negative node affinity, at least 2 resources in a resource
  affinity, no more resources than nodes in an anti-affinity, ...). A rule that fails is refused with
  `Rule 'x' is invalid.`, without the reason (see the findings below). A rule that becomes infeasible later (a node
  removed, another rule changed) is listed with its `errors` and dropped by the CRM.

pvecontrol checks the common cases before the call, to tell which one fails.

## Decisions

- Every command in the `ha` group, prefixed (`resource-*`, `rule-*`), 2 levels.
- Qemu VMs only, as everywhere in pvecontrol: VMs are given by VMID, `ct:` resources are not listed.
- Writes ask for a confirmation (`--force` to skip), and exit 1 on an API error.
- The rules are always read from `cluster/ha/rules` by the new commands, whatever the version.

## Commands

```
pvecontrol ha resource-list                    # --columns, --filter, --sort-by, -o
pvecontrol ha resource-add VMID... [--state STATE] [--max-restart N] [--max-relocate N]
                           [--failback/--no-failback] [--auto-rebalance/--no-auto-rebalance] [--comment TEXT] [--force]
pvecontrol ha resource-set VMID... [same options] [--force]
pvecontrol ha resource-remove VMID... [--no-purge] [--force]
pvecontrol ha rule-list                        # --columns, --filter, --sort-by, -o
pvecontrol ha rule-add RULE --type node-affinity --resources VMIDS --nodes NODE[:PRIO],...
                           [--affinity positive|negative] [--strict/--no-strict] [--disable] [--comment TEXT] [--force]
pvecontrol ha rule-add RULE --type resource-affinity --resources VMIDS --affinity positive|negative
                           [--disable] [--comment TEXT] [--force]
pvecontrol ha rule-set RULE [--resources VMIDS] [--nodes ...] [--affinity ...] [--strict/--no-strict]
                           [--enable/--disable] [--comment TEXT] [--force]
pvecontrol ha rule-remove RULE [--force]
```

## Plan

### Phase 6: HA resources

- `src/pvecontrol/models/ha.py`: `PVEHaResource` (dataclass, defaults of the API filled in), columns `vmid`, `name`,
  `node`, `state` (requested), `ha_state` (current state in the HA manager), `max_restart`, `max_relocate`,
  `failback`, `auto_rebalance`, `rules` (the rules naming it), `comment`.
- `PVECluster.ha_resources`: built from `ha["resources"]`, the VMs and the manager status.
- `actions/ha.py`: `resource-list` through `add_list_resource_command()` (which gets a command name),
  `resource-add` (the VM exists, is not a template nor already a resource), `resource-set` (at least one option, an
  empty `--comment` deletes it), `resource-remove` (lists the rules that lose the resource).
- Tests, README (`### ha`), AGENTS.md.

### Phase 7: HA rules

- `PVEHaRule` in `models/ha.py`, columns `rule`, `type`, `affinity`, `resources` (VMIDs), `nodes`, `strict`, `state`
  (`enabled`, `disabled`), `errors`, `comment`.
- `rule-add`: `--nodes` and `--strict` only for node affinity, `--affinity` required for resource affinity, VMIDs given
  as `100,101`. `rule-set` reads the rule and refuses the options of the other type. `rule-remove`.
- `rule-list` prints the `errors` of a rule per option (`resources: rule is ineffective as there are less than two
  resources`).

### Phase 8: `ha_rules` sanity check

CRIT for an enabled rule with errors (the HA manager drops it: an anti-affinity is not enforced), WARN for a disabled
rule, OK otherwise.

## Pull request

In PR #124, after the node maintenance commits:

1. `fix(cli)`: a `list` command crashed on an empty list (`render_output()` read the columns from the first row),
   found with `ha rule-list` on a cluster without rules.
2. `feat(ha)`: phases 6 and 7, the resource and rule commands share `actions/ha_config.py` and `models/ha.py`.
3. `feat(sanitycheck)`: phase 8.

## Findings while testing on enix-devel-1

- A refused rule comes back as HTTP 500 `create ha rule failed: 400 Rule 'x' is invalid.`, without the `errors`
  hash: the error goes through the HA config lock, which keeps only the message. pvecontrol checks the common cases
  before the call (`models.ha.rule_conflicts()`: at least 2 resources in a resource affinity, no more resources than
  nodes in an anti-affinity, a single node affinity rule per resource, no priorities nor every node in a negative node
  affinity, a positive and a negative resource affinity sharing 2 resources), and points to the documentation for the
  others.
- `PUT /cluster/ha/rules/{rule}` accepts `type` (it must match the rule).
- `GET /cluster/ha/resources` only returns the options that are set.

## Verification

`pytest`, `black`, `pylint`; live on enix-devel-1 only, with the test VM `vm:101` and VMs the user names for the
affinity rules.
