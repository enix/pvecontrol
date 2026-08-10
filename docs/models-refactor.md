# Models refactor: findings and plan

Scope of the study: how models are built from API payloads, and what to do with
the `COLUMNS` module constants. Reference point for the "already tried" column
is PR #83 (`refactor/dataclasses`, plus the local `fix/pr83-review-findings`).

Everything below is based on `main` at 0.8.0 (116 tests passing).

---

## 1. Findings

### 1.1 There are four dialects for building a model from a payload

| Dialect | Models | Shape |
| --- | --- | --- |
| Positional args + a dict parameter literally named `kwargs` | `node`, `vm` | `PVENode(cluster, node, status, kwargs=node)`, then `kwargs.get("cpu", 0)` inline |
| `_default_kwargs` class dict + `setattr` loop | `backup_job`, `volume`, `storage`, `user` | `for k, v in self._default_kwargs.items(): self.__setattr__(k, kwargs.get(k, v))` |
| Explicit per-field `kwargs.get` with validation | `acl`, `group` | one `kwargs.get` per field, `raise ValueError` on bad input |
| Not payload-driven at all | `task` | built by decoding a UPID string, then `refresh()` from the API |

On top of that, the *call sites* in `cluster.py` differ too:

- `PVENode(self, node["node"], node["status"], kwargs=node)`: two keys passed
  positionally **and** the whole payload passed again as a dict.
- `PVEStorage(self.api, storage.pop("node"), storage.pop("id"), storage.pop("shared"), **storage)`:
  three keys popped out of the payload, the rest splatted.
- `PVEBackupJob(backup_job.pop("id"), **backup_job)`: same, one key.
- `PVEAcl(**entry)`, `PVEGroup(**g)`, `PVEUser(**u)`: everything splatted.
- `PVETask(self.api, task["upid"])`: one key, the rest of the payload discarded.

So there is no single answer to "what are the fields of a node", "where do
defaults live", or "what happens to an API key we don't know about". Depending
on the model, an unknown key is silently swallowed by `**kwargs`, silently
ignored by the `_default_kwargs` loop, or would raise `TypeError`.

Consequences worth naming:

- **Defaults live in three shapes**: a `_default_kwargs` dict, inline second
  arguments to `kwargs.get()`, and `utils.defaulter()` calls applied to the raw
  payload before it ever reaches a model.
- **`utils.defaulter()` exists only to paper over missing keys** before
  construction (`cluster.resources_nodes`, `cluster.resources_vms`,
  `cluster.resources_storages`, `node.resources_vms`). It mutates the payload
  dicts in place, so `cluster.resources` is progressively rewritten by property
  access. Declared field defaults make it redundant.
- **API-shape to domain-shape conversion is scattered and inconsistent**:
  `status.upper()` into an enum (node, vm), `shared` int into a string via
  `STORAGE_SHARED_ENUM[shared]` (storage), `0`/`1` into bool (acl `propagate`,
  user `enable`, backup job `all`), comma strings into lists (user `groups`,
  group `users`, backup job `vmid`/`exclude`), a semicolon string into a set (vm
  `tags`), `maxcpu` renamed to `cpus` (vm). Some happen in `__init__` after the
  setattr loop, some inline, some at the call site.
- **Dashed API keys have no story**: `next-run`, `notes-template`,
  `prune-backups`, `realm-type` are not valid identifiers. `_default_kwargs`
  stores them as attribute names anyway (via `setattr`), so `job.next_run` does
  not exist and `getattr(job, "next-run")` is the only way to read it.
- `PVEUser` carries a `# pylint: disable=access-member-before-definition` that
  exists purely because the setattr loop hides the assignments from pylint.

### 1.2 `COLUMNS` is not a model description, it is a view specification

This matters, because the obvious idea ("derive the columns from the fields")
does not survive contact with the code.

- `storage`'s `COLUMNS` contains `nodes` and `usage`, which are **not attributes
  of `PVEStorage` at all**. They only exist in the dicts built by
  `PVEStorage.get_flattened_grouped_list()`, which is what `storage list` feeds
  on. So the rows of a list command are not always model instances.
- `node`'s `COLUMNS` contains `allocatedcpu` / `allocatedmem`, which are derived
  values, not payload values.
- `vm`'s `COLUMNS` contains `cpus`, which is `maxcpu` under another name.
- Field order in a model has nothing to do with column order.

`COLUMNS` is consumed in exactly two places, and both go through attribute names
as strings:

1. `cli.add_list_resource_command()`:
   `dict((k, item.__dict__[k] if hasattr(item, "__dict__") else item[k]) for k in default_columns)`
2. `cli.with_table_options()`: validates `--columns` and builds the `--sort-by`
   choices.

That first line carries a hard constraint most people miss:

> **A column can only name a stored instance attribute.** `item.__dict__[k]`
> raises `KeyError` for a `@property`.

That single constraint explains several odd shapes in the codebase:
`allocatedcpu`/`allocatedmem` are *stored* on `PVENode` rather than computed;
`usage` is precomputed into a dict; `percentage` (a real property) can never be
a column.

### 1.3 Requirements any replacement must satisfy

Collected from the code, not invented:

- **R1** order and default visible set for `<resource> list`.
- **R2** feed `--columns` validation and `--sort-by` choices (`cli.py`).
- **R3** sort on the **raw** value while displaying the **formatted** one.
  `prepare_prettytable` captures `line["sortby"] = line[sortby]` *before* the
  `naturalsize` pass, so `--sort-by maxmem` sorts numerically today. Any
  refactor that formats first breaks this silently.
- **R4** per-column formatting. Today `utils.NATURALSIZE_KEYS` is a global list
  of attribute names (`mem`, `maxmem`, `disk`, `maxdisk`, ...) applied to every
  model. Any model that grows a `mem` attribute gets humanized whether it means
  bytes or not, and a byte field under another name never is.
- **R5** columns must be able to name computed values, not just stored ones
  (see 1.2).
- **R6** rows are not always model instances: `storage list` rows are dicts, and
  `report.py` builds ad-hoc dicts and passes them to the same `render_output`.
- **R7** `--filter` matches against the **formatted** string (the filter pass
  runs after `naturalsize` in `prepare_prettytable`), so `--filter maxmem '32.0 GiB'`
  works and the raw byte count does not. Changing this changes user-visible
  behaviour.

### 1.4 Bugs and warts found along the way

Not all in scope, but they either motivate the refactor or are traps for it.

| # | Where | What |
| --- | --- | --- |
| W1 | `storage.get_flattened_grouped_list` | `item.pop("storage").__dict__` returns the **live** attribute mapping, and `storage.pop("node")` deletes `node` from the object. `report.py` carries a comment ordering its calls around this. PR #83 already fixes it. |
| W2 | `cluster._initstatus`, `cluster.backup_jobs` | Construction pops keys out of the API payload dicts. For storages those dicts are elements of `self.resources`, so `cluster.resources` is mutated as a side effect of building models. |
| W3 | `storage.details` | `__init__` sets `self._details = {}`, the property tests `if self._details is None`, so the lazy fetch is unreachable. The property is also unused. Dead and broken. |
| W4 | `cli.with_table_options` | `--columns` only accepts names from the default list, so `uptime`, `pool`, `lock`, `cpu`, `disk` are unreachable from the CLI even though the models carry them. |
| W5 | `utils.render_output` | Rows are built from `__dict__` wholesale, so `_api`, `_content`, `_details` land in the row dicts (excluded from display by prettytable's `fields=`, but present in the intermediate data). |
| W6 | `utils.prepare_prettytable` | `table[0].keys()` raises `IndexError` on an empty result set. |
| W7 | `storage.shared` | Stored as a string via `STORAGE_SHARED_ENUM[shared]`, then read back with `StorageShared[storage.shared.upper()]` in the sanity checks: a round trip through a string for an enum that already exists. |
| W8 | `report.py` | Calls `naturalsize()` by hand in six places, duplicating what `NATURALSIZE_KEYS` does for the list commands. Two code paths format the same quantities. |

---

## 2. Options for initialization

### A. Uniformize the current style (no dataclasses)

Give every model a `FIELDS` dict and a `from_api()` classmethod, keep the
setattr loop.

- Cost: near zero, no dependency, works everywhere.
- Gain: consistency, and that is all. No types, no `__repr__`/`__eq__`, the
  field list is a hand-maintained dict, and the setattr loop is exactly the kind
  of shared indirection that hides per-field intent (it is also what forces the
  `access-member-before-definition` disable).
- **Verdict**: the baseline to beat. It fixes the symptom, not the structure.

### B. Dataclasses, data/behaviour split (what PR #83 does)

`PVENodeData` (the `@dataclass`) + `PVENode(PVENodeData)` (the behaviour), with
a hand-written `__init__` calling `super().__init__(**kwargs)`.

What is genuinely good in PR #83 and worth keeping in any option:

- `api_kwargs(cls, payload)`: filters a payload down to declared field names and
  translates dashes to underscores, logging what it drops. It is a *filter*, not
  a converter, so it does not hide per-model conversion.
- One explicit `from_api()` classmethod per model, holding that model's own
  conversions with a comment saying what the API sends.
- `format_fields(instance)` replacing the `_default_kwargs`-driven `__str__`.
- Fixing W1.

What does not hold up:

- **Ten extra classes for nothing.** The split exists only to get a generated
  `__init__` and then override it. The override then re-validates and mutates,
  so the generated one is a private implementation detail of the subclass.
- **`fields()` stops meaning "the data".** `PVENodeData` declares `cluster: Any`
  and `vms: List` as fields (a back-reference and a computed collection), while
  `PVEVm.cpus`, `PVEStorage.short_id` and `PVENode.version` are set in
  `__init__` and are *not* fields. So `fields()` is neither the payload, nor the
  attributes, nor the columns. `format_fields()` therefore renders an arbitrary
  subset, and any future field-driven feature inherits that ambiguity.
- `field(default="")` is written out everywhere a bare `= ""` would do.
- The subclass is not itself a dataclass, so `@dataclass`-aware tooling
  (`asdict`, `replace`, `repr`, `eq`) operates on the parent's terms.

**Verdict**: right direction, one class too many, and the field set is not
disciplined.

### C. Dataclasses, one class per model

A single `@dataclass class PVENode:` with:

- fields = the data, with defaults declared once;
- `__post_init__` = validation and derivation that needs no collaborator;
- `from_api()` classmethod = the API-shape to domain-shape conversion, explicit
  per model;
- collaborators (`api`, `cluster`) declared as `ClassVar[Any] = None` and
  assigned by `from_api()`. `ClassVar` is excluded from `fields()` by
  `dataclasses` (verified), so `fields()` becomes exactly "the data", and pylint
  is happy because the class attribute exists.

Trade-off to accept: `__post_init__` runs inside the generated `__init__`, so it
cannot see a collaborator assigned afterwards. Anything needing the API at build
time (`node.version`, `node.vms`, `task.refresh()`) moves into `from_api()`
after attachment. That is arguably clearer: `from_api()` becomes the single
"assemble this from the remote" story.

Alternative to `ClassVar` if that reads as too clever:
`field(default=None, repr=False, compare=False)` and filter by a metadata
marker. It keeps collaborators in `fields()`, which is the thing we are trying
to avoid.

- Cost: same declaration volume as B minus one class per model, no dependency,
  Python 3.9 compatible.
- **Verdict: recommended.**

### D. attrs

Same shape as C plus `converter=`, `alias=`, `validator=`, and `slots=True` on
3.9.

The headline feature is the one we should *not* want: a `converter` fires on
every construction, so `PVEUser(groups="a,b")` and `PVEUser(groups=["a","b"])`
both become valid. That erases the distinction between "the shape the API
sends" and "the shape our constructor takes", which is precisely the
distinction the PR #83 review settled on. Plus a new runtime dependency for a
CLI whose current dependency list is deliberately small.

**Verdict**: no.

### E. pydantic v2

`BaseModel`, `Field(alias="next-run")`, `field_validator(mode="before")`,
`model_dump()`, `extra="ignore"`.

- Real gains: dashed keys handled declaratively (kills the `api_kwargs` dash
  translation), unknown keys handled by config, coercion by annotation, and
  `model_dump(mode="json")` would simplify the JSON/YAML output path
  substantially.
- Real costs: a compiled dependency (`pydantic-core`) for a 850-line model
  layer; errors become `ValidationError` instead of `ValueError`, changing both
  the tests and the CLI error UX; and `mode="before"` validators reintroduce the
  same "accepts both shapes" ambiguity as attrs unless carefully disciplined.
- It does not remove `from_api()`, it relocates it into decorators.

**Verdict**: the right answer *if* pvecontrol grows to cover a large slice of
the PVE API, where declarative aliases and validators scale better than
hand-written converters. For ten models today, it is a big hammer. Worth
revisiting, not now.

### F. msgspec / cattrs

`msgspec.Struct` with `rename=` is fast and 3.9-compatible, but adds a compiled
dependency and is niche. `cattrs` is philosophically close (a `structure` hook
*is* `from_api()`), but the hooks live in a converter registry, i.e. moved away
from the class into shared indirection.

**Verdict**: no.

### G. TypedDict + plain functions

Drop the model layer, keep payload dicts with typing. Loses the methods that
carry real logic (`is_selection_matching`, `migrate`, `get_backup_jobs`).

**Verdict**: no.

### H. NamedTuple

Immutable. `actions/node.py` does `target.allocatedcpu += vm.cpus` while
planning an evacuation, so models must stay mutable.

**Verdict**: no.

### I. A hand-rolled descriptor / mini-ORM

`maxmem = IntField(default=0, api_key="maxmem", column=True, render=BYTES)`,
unifying both problems in one declaration. Tempting, and it is the idea most
people reach for first.

It dies on three points: it reimplements `dataclasses` badly (`__set_name__`,
ordering, `__init_subclass__`); it forces every column to be a field, which
breaks the `storage list` case where `nodes` is not on the model at all (1.2);
and it couples the data declaration to the view, so the view's churn rewrites
the model.

**Verdict**: no, but worth naming so it is not re-proposed.

---

## 3. Options for `COLUMNS`

### 1. Just move it onto the class

`PVENode.COLUMNS` instead of a module constant. Removes the awkward double
import in every action (`from pvecontrol.models.node import COLUMNS` on a line
of its own, next to an import of the same module). Solves nothing else.

**Verdict**: necessary but not sufficient; fold it into option 3.

### 2. Derive columns from dataclass field metadata

`maxmem: int = field(default=0, metadata={"column": 3, "render": BYTES})`.

Single declaration site and a typo becomes impossible. But it fails R5 and R6
outright: a property cannot be a field, and `storage list`'s `nodes` column is
not on the model. It also pushes view concerns into the data declaration, which
then also drives `asdict`/`__str__`. Ordering via an integer in an untyped dict
is unpleasant.

**Verdict**: no. This is the option that looks cleanest on paper and breaks on
`storage`.

### 3. An explicit `Column` object list, declared next to the model

```python
@dataclass
class PVENode:
    COLUMNS: ClassVar[List[Column]] = [
        Column("node"),
        Column("status"),
        Column("allocatedcpu"),
        Column("maxcpu"),
        Column("mem", render=BYTES),
        Column("allocatedmem", render=BYTES),
        Column("maxmem", render=BYTES),
    ]
```

with a small `Column` in the output layer:

```python
@dataclass(frozen=True)
class Column:
    name: str
    render: Optional[Callable] = None

    def value(self, item):    # raw, used for sorting (R3)
        return item[self.name] if isinstance(item, Mapping) else getattr(item, self.name)

    def display(self, item):  # formatted, used for the cell and for filtering (R4, R7)
        ...
```

Satisfies R1 to R7: `getattr` makes properties usable (R5), the `Mapping`
fallback makes dict rows work unchanged (R6), `value()` vs `display()` keeps raw
sorting with formatted display (R3), and `render=` per column deletes
`NATURALSIZE_KEYS` (R4).

The one weakness: column names are strings, so a typo is a runtime
`AttributeError`. Mitigation is one cheap test per model that resolves every
declared column against a built fixture instance.

**Verdict: recommended**, combined with option 1 (declare it as a `ClassVar` on
the model).

### 4. A view/serializer class per model

`class NodeTable(Table): ...`. Same as 3 with more ceremony, for one list
command per resource.

**Verdict**: no.

### 5. A column registry in the output layer

`COLUMN_RENDERERS = {"maxmem": BYTES, ...}` keyed by attribute name. This is
what `NATURALSIZE_KEYS` already is, generalized: it couples unrelated models by
attribute name and is the thing we are removing.

**Verdict**: no.

### 6. Drop `COLUMNS`: show every field by default

Attractive minimalism, but `node list` would then show `cpu`, `disk`,
`maxdisk`, `version`, `vms`, and `vm list` would show `lock`, `uptime`, `pool`.
The current lists are deliberate curation.

A **variant is worth keeping** though, and it fixes W4: let the model declare
*all* renderable columns and a `DEFAULT_COLUMNS` subset shown by default, so
`--columns uptime,pool` finally works. Cheap on top of option 3.

**Verdict**: not as stated; take the variant as an optional extra.

---

## 4. Recommendation

**C + 3**: one dataclass per model with an explicit `from_api()`, and a
`ClassVar` list of `Column` objects as the view spec.

What that buys, concretely:

- One place per model says what its fields are, with types and defaults.
- One place per model says how the API shape becomes the domain shape, per
  field, with a comment. No conversion is hidden in a shared helper.
- `fields()` means exactly "the data", so `__str__`, JSON output and any future
  field-driven feature are trustworthy.
- `utils.NATURALSIZE_KEYS` is deleted.
- `utils.reorder_keys` is deleted (rows are built in column order).
- `cli.add_list_resource_command`'s row-building comprehension is deleted, along
  with the `__dict__` access, which fixes W5 and lifts the "stored attributes
  only" constraint.
- `utils.defaulter` is deleted once `cluster.{cpu,memory,disk}_metrics` read the
  model objects instead of the raw payload dicts (their defaults then come from
  the fields).
- `PVEStorage.short_id`, `.percentage` and a new `.usage` become properties and
  therefore usable as columns, which shrinks `get_flattened_grouped_list` and
  removes W1.
- W3, W7, W8 get fixed on the way through.

One thing that must **not** change: `PVENode.allocatedcpu` / `allocatedmem`
have to stay assignable fields, not properties. `actions/node.py` mutates them
to simulate allocation while planning an evacuation.

### North star, optional

Half the model methods already take the cluster as an argument
(`get_backup_jobs(proxmox)`, `get_backups(proxmox)`, `get_last_backup(proxmox)`,
`get_members(proxmox)`, `get_groups(proxmox)`). Only `PVEVm.config`/`migrate`,
`PVEStorage.get_content`/`images`, `PVENode.api`/`resources`/`version` and
`PVETask` hold an API handle on the instance.

Finishing that convention (models are data plus logic, the cluster owns all IO)
would make every `from_api(cls, payload)` signature identical, with no `api` or
`cluster` parameter and no `ClassVar` collaborators at all. That is the real
prize for "uniform initialization". It also touches `sanitycheck/` and
`actions/`, so it should be its own change, after the rest has landed.

---

## 5. Plan

Six steps, each independently reviewable and independently valuable. Steps 1
and 2 are orthogonal and can land in either order.

**Step 0: safety net.** The model layer has thin tests (`test_acl`, `test_group`,
`test_user`, `test_backup_job` are the only per-model ones; `test_report.py` is
the broadest coverage at 374 lines). Before touching anything, add
characterization tests that render each `<resource> list` in all five output
formats against the existing fixtures in `tests/fixtures/api.py`, and assert on
the exact strings. That is what will catch R3 and R7 regressions, which are the
easy ones to break silently.

**Step 1: introduce `Column` (no model changes).** Add `Column` next to
`render_output` in `utils.py`, teach `render_output`/`prepare_prettytable`/
`with_table_options`/`add_list_resource_command` to consume it, and turn the
existing `COLUMNS` module constants into lists of `Column`. Delete
`NATURALSIZE_KEYS` and `reorder_keys`. No model is touched. This step alone
fixes W5, lifts the stored-attributes-only constraint, and is a small diff.

**Step 2: convert the models, one commit each.** Order by dependency, simplest
first: `volume`, `acl`, `group`, `user`, `backup_job`, then `vm`, `node`,
`storage`, `task`, then `cluster` (the caller). Each commit: single `@dataclass`,
`__post_init__` validation, `from_api()` conversion, collaborators as
`ClassVar`, `__str__` via `format_fields()` where it was `_default_kwargs`
driven. Keep PR #83's `api_kwargs()` and `format_fields()` helpers in
`models/__init__.py`.

**Step 3: move the column lists onto the model classes** as `ClassVar`s, and
update the actions to import only the model. One small commit.

**Step 4: the cleanups this unlocks.** Delete `utils.defaulter` (move the
cluster metrics onto the model objects); make `short_id`/`usage` properties and
simplify `get_flattened_grouped_list`; fix W3 (`storage.details`) and W7
(`shared` as a real enum, updating `sanitycheck/tests/vm.py` and
`sanitycheck/tests/ha_vms.py`); stop popping keys out of the API payloads (W2).

**Step 5, optional: `--columns` accepts any declared column** (W4), via
`COLUMNS` + `DEFAULT_COLUMNS`.

**Step 6, optional: drop the API handles from the models** (the north star
above).

### What to do with PR #83

Do not throw it away and do not merge it as is. It is Step 2 with an extra class
per model. Concretely:

- Keep: `api_kwargs()`, `format_fields()`, the per-model `from_api()` split, the
  W1 fix, and the new tests (`test_models`, `test_node`, `test_storage`,
  `test_vm`, `test_volume`).
- Rework: collapse each `PVEXData` + `PVEX` pair into one dataclass; move
  `cluster`/`_api`/`vms` out of `fields()`; drop the redundant `field(default=…)`
  wrappers; decide per model whether a value is a field, a property or a
  collaborator, and make `fields()` mean one thing.
- Land Step 1 first, since it is independent of PR #83 and shrinks what PR #83
  has to touch.
