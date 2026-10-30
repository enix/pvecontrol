# Proxmox VE Control

![release workflow](https://github.com/enix/pvecontrol/actions/workflows/release.yml/badge.svg?branch=main)
![PyPI release](https://img.shields.io/pypi/v/pvecontrol.svg)
![PyPI downloads](https://img.shields.io/pypi/dm/pvecontrol.svg)

`pvecontrol` (<https://pypi.org/project/pvecontrol/>) is a CLI tool to manage Proxmox VE clusters and perform intermediate and advanced tasks that aren't available (or aren't straightforward) in the Proxmox web UI or default CLI tools.

It was written by (and for) teams managing multiple Proxmox clusters, sometimes with many hypervisors. Conversely, if your Proxmox install consists of a single cluster with a single node, the features of `pvecontrol` might not be very interesting for you!

Here are a few examples of things you can do with `pvecontrol`:

- List all VMs across all hypervisors, along with their state and size; list nodes, storages, tasks, users, groups and ACLs the same way;
- Evacuate (=drain) a hypervisor, i.e. migrate all VMs that are running on that hypervisor, automatically picking nodes with enough capacity to host these VMs.
- Run sanity checks on a cluster. Sanity checks are sets of tests designed to verify the integrity of the cluster.
- Generate a Markdown report of a whole cluster, sanity checks included.

To communicate with Proxmox VE, `pvecontrol` uses [proxmoxer](https://pypi.org/project/proxmoxer/), a wonderful library that enables communication with various Proxmox APIs.

### Scope

`pvecontrol` only manages **Qemu virtual machines**. LXC containers are ignored everywhere: they don't appear in lists, they are not counted in node capacity (allocated CPU and memory), and the sanity checks and the report don't look at them.

### Supported Proxmox VE versions

`pvecontrol` targets the Proxmox VE versions that are still supported upstream (see <https://endoflife.date/proxmox-ve>), which means 9.x today. Versions that reached their end of life may keep working, but `pvecontrol` is not adjusted for them anymore.

## Installation

`pvecontrol` requires Python version 3.10 or above.

The easiest way to install it is simply using pip. New versions are automatically published to [pypi](https://pypi.org/project/pvecontrol/) repository. It is recommended to use `pipx` in order to automatically create a dedicated python virtual environment:

```shell
pipx install pvecontrol
```

## Configuration

To use `pvecontrol`, you must create a YAML configuration in `$HOME/.config/pvecontrol/config.yaml`. That file will list your clusters and how to authenticate with them.

`pvecontrol` only uses the Proxmox HTTP API, which means that you can use most Proxmox authentication mechanisms, including `@pve` realm users and tokens.

HTTPS certificate verification is disabled by default, but can be enabled using the `ssl_verify` boolean.

It is strongly recommended to create a dedicated Proxmox user for `pvecontrol` rather than using an existing admin account. This limits the blast radius in case of misconfiguration or credential leak, and makes it easy to audit or revoke access. Here's how to set up a dedicated user and role:

```shell
pveum role add custom-PVEControl --privs "Datastore.Audit,Datastore.AllocateSpace,Datastore.AllocateTemplate,Pool.Audit,SDN.Audit,Sys.Audit,VM.Audit,VM.Allocate,VM.Backup,VM.Clone,VM.GuestAgent.Audit,VM.Migrate,VM.PowerMgmt,VM.Replicate,VM.Snapshot,VM.Snapshot.Rollback"
pveum user add pvecontrol@pve --password my.password.is.weak
pveum acl modify / --roles custom-PVEControl --users pvecontrol@pve
```

The `custom-PVEControl` role combines:
- `PVEAuditor`: read-only access to the Proxmox API
- `PVEVMAdmin`-like privileges: VM management, including migrations and power management (`VM.PowerMgmt`, used by `vm start`, `vm shutdown` and `vm stop`)
- `PVEDatastoreUser` extra privileges (`Datastore.AllocateSpace`, `Datastore.AllocateTemplate`): required to list backups on PBS (Proxmox Backup Server) storages

`vm unlock` is the exception: it only works when authenticated as `root@pam`, see [vm unlock](#vm-unlock).

You can then create the following configuration file in `$HOME/.config/pvecontrol/config.yaml`:

```yaml
clusters:
  - name: fr-par-1
    host: localhost
    user: pvecontrol@pve
    password: my.password.is.weak
    ssl_verify: true
```

And see `pvecontrol` in action right away:

```shell
pvecontrol -c fr-par-1 vm list
```

### API tokens

`pvecontrol` also supports authentication with API tokens. A Proxmox API token is associated to an individual user, and can be given separate permissions and expiration dates. You can learn more about Proxmox tokens in [this section of the Proxmox documentation](https://pve.proxmox.com/pve-docs/pveum-plain.html#pveum_tokens).

As an example, to create a new API token associated to the `pvecontrol@pve` user and inherit all its permissions, you can use the following command:

```shell
pveum user token add pvecontrol@pve mytoken --privsep 0
```

Then, retrieve the token value, and add it to the configuration file to use it to authenticate:

```yaml
clusters:
  - name: fr-par-1
    host: localhost
    user: pvecontrol@pve
    token_name: mytoken
    token_value: randomtokenvalue
```

`password` and `token_name` / `token_value` can't be used together, and `token_name` requires `token_value`. `user` is required in both cases.

### Reverse proxies

`pvecontrol` supports certificate-based authentication to a reverse proxy. Which makes it suitable for use with tools like [teleport](https://goteleport.com/docs/enroll-resources/application-access/guides/connecting-apps/) using teleport apps.

Give the paths of the client certificate and of its key under `proxy_certificate`:

```yaml
clusters:
  - name: fr-par-1
    host: localhost
    user: pvecontrol@pve
    password: my.password.is.weak
    proxy_certificate:
      cert: /tmp/proxmox-reverse-proxy.pem
      key: /tmp/proxmox-reverse-proxy
```

You can also use command substitution syntax and the key `proxy_certificate` to execute a command that will output a JSON document containing the certificate and key paths.

```yaml
clusters:
  - name: fr-par-1
    host: localhost
    user: pvecontrol@pve
    password: my.password.is.weak
    proxy_certificate: $(my_custom_command login proxmox-fr-par-1)
```

It should output something like this:

```json
{
  "cert": "/tmp/proxmox-reverse-proxy.pem",
  "key": "/tmp/proxmox-reverse-proxy",
  "anything_else": "it is ok to have other fields, they will be ignored. this is to support existing commands"
}
```

CAUTION: environment variable and `~` expansion are not supported in the certificate and key paths.

### Better security

Instead of specifying users, passwords, tokens and certificates paths in plain text in the configuration file, you can use the shell command substitution syntax `$(...)` inside the `user`, `password`, `token_name`, `token_value` and `proxy_certificate` fields; for instance:

```yaml
clusters:
  - name: prod-cluster-1
    host: 10.10.10.10
    user: pvecontrol@pve
    ssl_verify: true
    password: $(command to get -password)
```

The whole value must be a `$(...)` expression; the command runs in a shell, and `pvecontrol` stops with an error if it fails.

### Worse security

You _can_ use `@pam` users (and even `root@pam`) and passwords in the `pvecontrol` YAML configuration file; but you probably _should not_, as anyone with read access to the configuration file would then automatically gain shell access to your Proxmox hypervisor. _Not recommended in production!_

### Advanced configuration options

The configuration file can include a `node:` section to specify CPU and memory policies. These will be used when scheduling a VM (i.e. determine on which node it should run), specifically when draining a node for maintenance, and by the `nodes` sanity check.

There are currently two parameters: `cpufactor` and `memoryminimum`.

`cpufactor` indicates the level of overcommit allowed on a hypervisor. `1` means no overcommit at all; `5` means "a hypervisor with 8 cores can run VMs with up to 5x8 = 40 cores in total". The default is `2.5`.

`memoryminimum` is the amount of memory that should always be available on a node, in bytes. When scheduling a VM (for instance, when automatically moving VMs around), `pvecontrol` will make sure that this amount of memory remains available for the hypervisor OS itself. The default is `8589934592` (8 GiB). Caution: if that amount is set to zero, it will be possible to allocate the entire host memory to virtual machines, leaving no memory for the hypervisor operating system and management daemons!

The CPU and memory allocated on a node are the sums of the vCPUs and memory of its **running** VMs.

A `vm:` section holds the VM policies. There is currently one parameter: `max_last_backup`, the age in minutes after which the last backup of a VM is considered too old by the `vm_backups` sanity check. The default is `1500` (25 hours).

These options can be specified in a global `node:` / `vm:` section, and then overridden per cluster. A value set for a cluster always wins over the global one, even an explicit `0`. A per-cluster `vm:` section must set `max_last_backup`.

Here is a configuration file showing this in action:

```yaml
---
node:
  # Overcommit CPU factor
  # 1 = no overcommit
  cpufactor: 2.5
  # Memory to reserve for the system on a node (in bytes)
  memoryminimum: 8589934592
vm:
  # Age of the last backup of a VM, in minutes, after which it is too old
  max_last_backup: 1500
clusters:
  - name: my-test-cluster
    host: 192.168.1.10
    user: pvecontrol@pve
    password: superpasssecret
    # Override global values for this cluster
    node:
      cpufactor: 1
    vm:
      max_last_backup: 10080
  - name: prod-cluster-1
    host: 10.10.10.10
    user: pvecontrol@pve
    password: Supers3cUre
    timeout: 120
  - name: prod-cluster-2
    host: 10.10.10.10
    user: $(command to get -user)
    password: $(command to get -password)
  - name: prod-cluster-3
    host: 10.10.10.10
    user: morticia@pve
    token_name: pvecontrol
    token_value: 12345678-abcd-abcd-abcd-1234567890ab
```

### Configuration reference

Each entry of `clusters:` accepts these keys:

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `name` | yes | | Name of the cluster for `-c` / `--cluster` (matched case-insensitively) |
| `host` | yes | | Host of the Proxmox API |
| `user` | yes | | Proxmox user, e.g. `pvecontrol@pve`; supports `$(...)` |
| `password` | | | Password of the user; supports `$(...)` |
| `token_name` | | | Name of an API token of the user, instead of a password; supports `$(...)` |
| `token_value` | | | Secret of that API token; supports `$(...)` |
| `proxy_certificate` | | | Client certificate for a reverse proxy: a `cert` / `key` mapping of paths, or a `$(...)` command printing them as JSON |
| `timeout` | | `60` | Timeout of the API requests, in seconds |
| `ssl_verify` | | `false` | Verify the HTTPS certificate of the API |
| `node` | | global `node:` | Per-cluster `cpufactor` / `memoryminimum` |
| `vm` | | global `vm:` | Per-cluster `max_last_backup` |

At the top level, `node:` (`cpufactor`, `memoryminimum`) and `vm:` (`max_last_backup`) set the defaults of every cluster, as described above.

## Usage

Here is a quick overview of `pvecontrol` commands and options, it may evolve over time:

```shell
$ pvecontrol --help
Usage: pvecontrol [OPTIONS] COMMAND [ARGS]...

  Proxmox VE control CLI, version: x.y.z

Options:
  -d, --debug
  -o, --output [text|json|csv|yaml|md]
                                  [default: text]
  -c, --cluster NAME              Proxmox cluster name as defined in
                                  configuration
  --unicode / --no-unicode        Use unicode characters for output
  --color / --no-color            Use colorized output
  --config PATH                   Path to configuration file (overrides
                                  default
                                  ~/.config/pvecontrol/config.yaml)
  --help                          Show this message and exit.

Commands:
  acl list       List acls in the cluster
  group list     List groups in the cluster
  node evacuate  Evacuate a node by migrating all it's VM out to one or...
  node list      List nodes in the cluster
  report         Generate a resource usage report for the cluster
  sanitycheck    Check status of proxmox Cluster
  status         Show cluster status
  storage list   List storages in the cluster
  task get       Get detailled information about a task
  task list      List tasks in the cluster
  user list      List users in the cluster
  vm list        List VMs in the cluster
  vm migrate     Migrate VMs in the cluster
  vm restore     Restore a VM from a backup archive
  vm shutdown    Cleanly shutdown a VM
  vm start       Start a VM
  vm stop        Stop a VM
  vm unlock      Remove the lock set on a VM

  Made with love by Enix.io
```

`pvecontrol` works with subcommands for each operation. Operation related to a specific kind of object (tasks for instance) will be grouped into their own subcommand group. Each subcommand has its own help, which works without any cluster configured:

```shell
$ pvecontrol task get --help
Usage: pvecontrol task get [OPTIONS] UPID

  Get detailled information about a task

Options:
  -f, --follow  Follow task log output
  -w, --wait    Wait task end
  --help        Show this message and exit.
```

The `-c` or `--cluster` flag indicates on which cluster we want to work. It can be omitted when exactly one cluster is configured: that cluster is then used. With no cluster configured, or several clusters and no `-c`, `pvecontrol` stops with an error listing the available clusters. The cluster can also be set with the `PVECONTROL_CLUSTER` environment variable.

Logs, warnings and errors are written on stderr, so `-o json` (or `csv`, `yaml`) output on stdout can be piped as is. `-d` / `--debug` enables debug logs. Errors end with exit code `1`: a VM or node that doesn't exist, an error returned by the Proxmox API, a declined confirmation, or a task that failed while waited for (see [Tasks](#tasks)).

The simplest operation we can do to check that `pvecontrol` works correctly, and that authentication has been configured properly is `status`:

```shell
$ pvecontrol --cluster my-test-cluster status
INFO:root:Proxmox cluster: my-test-cluster

  Name: my-test-cluster
  Version: 9.1.4
  Status: healthy
  VMs: 18
  Templates: 11
  Metrics:
    CPU: 0.15/96 (0.2%), allocated: 33
    Memory: 34.23 GiB/440.51 GiB(7.8%), allocated: 58.00 GiB
    Disk: 1.61 TiB/24.00 TiB(6.7%)
  Nodes:
    Offline: 0
    Online: 3
    Unknown: 0
```

If this works, we're good to go! `Status` is `healthy` when the cluster has quorum.

### Listing resources

`vm list`, `node list`, `storage list`, `task list`, `user list`, `group list` and `acl list` all list resources of the whole cluster, and share the same options:

- `--columns COL1,COL2,...` to choose the columns to display (and their order);
- `--sort-by COLUMN` to sort the rows;
- `--filter COLUMN REGEXP` to keep only the rows where `COLUMN` matches the regular expression, can be given several times (all filters must match);
- the global `-o` / `--output` option to get `text`, `json`, `csv`, `yaml` or `md` (Markdown) output.

```shell
$ pvecontrol vm list --filter node 'pve-node-1$' --filter status RUNNING --columns vmid,name,maxmem
```

`vm list` also lists templates. `storage list` shows a shared storage once, with the list of its nodes.

### vm migrate

`vm migrate VMID --target NODE` migrates a VM to another node. Use `--online` for a live migration of a running VM. Disks on local storages are migrated along (`with-local-disks`). `--dry-run` runs the Proxmox migration precheck but doesn't start the migration. Unlike `node evacuate`, `vm migrate` does not check that the target node has enough CPU or memory left.

```shell
$ pvecontrol vm migrate 100 --target pve-node-2 --online --wait
```

### vm start, vm shutdown, vm stop

`vm start`, `vm shutdown` (clean ACPI shutdown, `--timeout SECONDS` to bound it) and `vm stop` (hard stop, `--overrule-shutdown` to override a shutdown in progress) change the power state of a VM. They ask for confirmation, unless `--force` is given; declining it exits with code 1. `--dry-run` only shows what would be done. Nothing is done if the VM is already in the requested state.

```shell
$ pvecontrol vm shutdown 100 --timeout 120 --wait
Shutting down VM 100 (vm-100)
Confirm [y/N]: y
```

### vm restore

`vm restore VMID --target NODE --archive ARCHIVE` creates a VM from a backup archive on the given node. `ARCHIVE` is a backup volume identifier (as shown by Proxmox, e.g. `pbs:backup/vm/100/2025-01-01T00:00:00Z`) or the path of a `.tar` / `.vma` file. `--storage` selects the storage for the disks (the one from the backup by default), `--force` overwrites an existing VM with the same id.

```shell
$ pvecontrol vm restore 200 --target pve-node-1 --archive 'pbs:backup/vm/100/2025-01-01T00:00:00Z' --storage local-lvm --wait
```

### vm unlock

`vm unlock` removes the lock set on a VM, it is the equivalent of `qm unlock <vmid>`. The lock is never removed
automatically: the current lock is displayed and confirmation is asked before anything is done. Declining it exits
with code 1, and so does a VM that is not found. A VM that is not locked is not an error: there is nothing to do.

```shell
$ pvecontrol --cluster my-test-cluster vm unlock 100
Removing lock 'backup' on VM 100 (vm-100)
Confirm [y/N]: yes
Lock 'backup' removed from VM 100 (vm-100)
```

Use `--dry-run` to display the lock that would be removed without removing it for real (the confirmation is still
asked), and `--force` to skip the confirmation prompt, for non interactive usage:

```shell
$ pvecontrol --cluster my-test-cluster vm unlock 100 --force
Removing lock 'backup' on VM 100 (vm-100)
Lock 'backup' removed from VM 100 (vm-100)
```

**This command only works with the `root@pam` user.** It calls `PUT /nodes/{node}/qemu/{vmid}/config` with
`delete=lock` and `skiplock=1`: `skiplock` is required to modify the configuration of a locked VM, and the Proxmox
API rejects it for any other user with `Only root may use this option`. This restriction is hardcoded in the API
source (`PVE::API2::Qemu`, `raise_param_exc` on `skiplock` when `$authuser ne 'root@pam'`), it is not tied to a
privilege or a role, so it cannot be granted to an API token or to a user with the `Administrator` role. This is
still true as of PVE 9.2.

Consequently the cluster used for `vm unlock` must be authenticated as `root@pam`, any other user or a
privilege separated token will fail whatever permissions it is granted.

### node evacuate

`node evacuate NODE [TARGET]...` drains a node: it migrates its VMs to other nodes, for instance before a maintenance.

```shell
$ pvecontrol node evacuate pve-node-1 'pve-node-*' --online --dry-run
INFO:root:Proxmox cluster: my-test-cluster
WARNING:root:Target node pve-node-1 is the same as source node, skipping
Migrating VM 1001 (vm-a) from pve-node-1 to pve-node-3
Migrating VM 1002 (vm-b) from pve-node-1 to pve-node-3
Migrating VM 1005 (vm-e) from pve-node-1 to pve-node-3
Confirm [y/N]: n
ERROR:root:Aborting
```

How it works:

- **Which VMs**: only the running VMs are migrated by default. Add `--no-skip-stopped` to migrate the stopped ones too.
- **`--online`**: Proxmox refuses to migrate a running VM offline, so running VMs are only migrated with `--online` (live migration). Without it they are skipped with a warning, and the node is not fully evacuated.
- **Targets**: by default, every other online node of the cluster. Targets can be given as node names or glob patterns (`'pve-node-*'`, quote them for your shell); the source node and nodes that are not online are skipped with a warning.
- **Placement**: greedy, VM after VM in the order Proxmox lists them, each VM going to the first target where it fits (targets are tried in no particular order). A VM fits when, with the VMs already placed there, the target keeps `memoryminimum` of memory free and stays within `cpufactor` times its CPUs (see [Advanced configuration options](#advanced-configuration-options)). A VM that fits nowhere is skipped with a warning.
- **Confirmation**: the planned migrations are displayed, then confirmation is always asked. Declining it exits with code 1.
- **`--dry-run`**: the plan is computed and displayed (and the confirmation asked) but no migration is started.
- **`--wait` / `--follow`**: wait for each migration to end, or follow its log, before starting the next one. Without them, migrations are started one after another and their result is not checked.
- **Exit code**: `1` when the node is not fully evacuated (a VM had no target, or a running VM was skipped because `--online` was missing) or when a migration waited for failed (see [Tasks](#tasks)); `0` otherwise. A node with nothing to migrate succeeds, even when no target is available.

The source node must be online.

### Tasks

`task list` lists the tasks of the cluster, `task get UPID` shows a task, its status and its log. With `--wait` (`-w`), `task get` waits for the end of a running task; with `--follow` (`-f`), it prints its log while it runs. The same options are available on the commands that start a task (`vm migrate`, `vm start`, `vm shutdown`, `vm stop`, `vm restore`, `node evacuate`).

Migrating a VM managed by HA starts a `hamigrate` task, which only asks the HA manager to migrate the VM and ends right away; the HA manager runs the actual migration in a task of its own a few seconds later. With `--wait` or `--follow`, `pvecontrol` finds that migration task and waits for it (or follows it) as well, then waits for the HA manager to record the end of the migration. Without them, only the `hamigrate` task is shown.

With `--wait` or `--follow`, the command exits with code 1 when the task failed: Proxmox ended it with any status other than `OK` or `WARNINGS: <count>`. A task that completed with warnings succeeded, its warnings are in its log. A task whose node can't be reached anymore also exits with code 1. Without `--wait` or `--follow`, the task is usually still running when the command returns, so its result is not checked.

### sanitycheck

`sanitycheck` runs a set of checks on the cluster and reports their results:

| Id | Type | What is verified |
|----|------|------------------|
| `nodes` | NODE | Every node is online (CRIT otherwise). The memory allocated to running VMs plus `memoryminimum` stays below the node memory (CRIT otherwise). The vCPUs allocated to running VMs stay below `cpufactor` times the node CPUs (WARN otherwise). |
| `ha_groups` | HIGH_AVAILABILITY | Every HA group (node-affinity rule since PVE 9.1) contains at least 2 nodes (CRIT otherwise). |
| `ha_vms` | HIGH_AVAILABILITY | VMs managed by HA have all their disks on shared storages (CRIT otherwise) and don't use the `host` CPU type (WARN otherwise). An HA resource without a matching VM is a WARN. |
| `vms_start_on_boot` | VIRTUAL_MACHINE | The `onboot` option ("Start at boot") of each VM, templates excluded, matches its state, see below. |
| `vm_backups` | VIRTUAL_MACHINE | Each VM is selected by at least one enabled backup job (WARN otherwise), and its last backup is more recent than `max_last_backup` minutes (CRIT if older, WARN if it was never backed up). |
| `disk_unused` | STORAGE | No VM has `unused` disks in its configuration, and no disk image on a storage belongs to a VM that doesn't exist (on that node for a local storage, in the cluster for a shared one): CRIT otherwise. Storages of type `s3` are not checked. |

`vms_start_on_boot` is opinionated: it expects running VMs to start at boot and stopped VMs not to. A stopped VM with `onboot=1`, or a running VM without it, is reported as CRITICAL.

Each check reports messages with one of these levels: `OK`, `INFO`, `WARN` (warning) or `CRIT` (critical). The status of a check is its worst message. Checks always run in the same order, grouped by type (NODE, HIGH_AVAILABILITY, VIRTUAL_MACHINE, STORAGE), followed by a summary. To run only some checks, give their ids:

```shell
$ pvecontrol --no-unicode sanitycheck nodes vms_start_on_boot
INFO:root:Proxmox cluster: my-test-cluster
------------------------------- NODE -------------------------------

Check Node capacity: [OK]

- Node 'pve-node-1' isn't in cpu overcommit.......................[OK]
- Node 'pve-node-2' isn't in cpu overcommit.......................[OK]
- Node 'pve-node-1' isn't in mem overcommit.......................[OK]
- Node 'pve-node-2' isn't in mem overcommit.......................[OK]

------------------------- VIRTUAL_MACHINE -------------------------

Check vms startonboot option: [CRIT]

- VM '100/vm-100' has the good 'startonboot' option...............[OK]
- VM '101/vm-101' is running but 'startonboot' is set to false....[CRIT]


----------------------------- SUMMARY -----------------------------

Total checks: 2
Critical: 1
Warning: 0
OK: 1
Info: 0
```

`sanitycheck` exits with code `1` when at least one CRIT message is found, `0` otherwise (warnings don't change the exit code), so it can be used in monitoring or CI.

A node that is not online is reported as CRIT by the `nodes` check. The VM configurations and storage contents of such a node can't be read, so the other checks report a WARN for what they couldn't verify on it, instead of failing.

### report

`report` generates a report of the whole cluster, in Markdown (`-o md`) or text (`-o text`, the default; other output formats are refused). It contains a header (cluster name, Proxmox VE version, health), a resource overview (CPU, memory and disk usage and allocation, VM and template counts), access control (users, groups, permissions), the nodes, HA groups, storages, backup jobs and VMs (with their HA group, tags and backup jobs), and the output of all the sanity checks.

```shell
$ pvecontrol -o md report > my-test-cluster.md
```

### Offline or rebooting nodes

Commands keep working when a node is down or rebooting. Proxmox still lists the VMs and storages of a node that is not online, with their last known values: `pvecontrol` shows that node as offline (or unknown) and its VMs with the `UNKNOWN` status, and doesn't send any request to it. Right after a node went down, or before its API is back, Proxmox may still list it online: `pvecontrol` then logs a warning and handles it as unknown.

Actions that need the node are refused with an error: `vm` commands on one of its VMs, `node evacuate` from it, or waiting for one of its tasks. It is skipped as a target of `node evacuate`.

## Environment variables

`pvecontrol` supports the following environment variables:
- `PVECONTROL_CLUSTER`: the default cluster to use when no `-c` or `--cluster` option is specified.
- `PVECONTROL_COLOR`: if set to `False`, it will disable all colorized output.
- `PVECONTROL_UNICODE`: if set to `False`, it will disable all unicode output.
- `PVECONTROL_CONFIG`: path to the configuration file to use instead of `~/.config/pvecontrol/config.yaml`, like `--config`.
- `PVECONTROL_OUTPUT`: the default output format, like `-o` / `--output`.
- `PVECONTROL_DEBUG`: if set to `True`, enable debug logs, like `-d` / `--debug`.

More generally, every option can be set with a `PVECONTROL_<COMMAND>_<OPTION>` variable, for instance `PVECONTROL_VM_LIST_SORT_BY=name` for `vm list --sort-by name`.

### Using another configuration file

`--config PATH` (or `PVECONTROL_CONFIG`) **replaces** `~/.config/pvecontrol/config.yaml`, it doesn't add to it: the given file is only layered on top of the default values shipped with `pvecontrol` (`cpufactor`, `memoryminimum`, `max_last_backup`), and nothing is read from your usual configuration file. The given file must therefore hold everything needed, clusters and credentials included.

This is deliberate: when two configuration files are merged, the `clusters:` lists are merged entry by entry, by position, so the first cluster of one file would be mixed with the first cluster of the other one.

## Shell completion

`pvecontrol` provides a completion helper to generate completion configuration for common shells. It currently supports `bash`, `zsh`, and `fish`.

You can adapt the following commands to your environment:

```shell
# bash
_PVECONTROL_COMPLETE=bash_source pvecontrol > "${BASH_COMPLETION_USER_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion}/completions/pvecontrol"
# zsh
_PVECONTROL_COMPLETE=zsh_source pvecontrol > "${HOME}/.zsh/completions/_pvecontrol"
# fish
_PVECONTROL_COMPLETE=fish_source pvecontrol > {$HOME}/.config/fish/completions/pvecontrol.fish
```

## Development

If you want to tinker with the code, all the required dependencies are listed in `requirements.txt`, and you can install them e.g. with pip:

```shell
pip3 install -r requirements.txt -e .
```

`requirements.lock.txt` holds the same runtime dependencies with their transitive closure pinned to exact versions. Install from it for a reproducible environment (it also feeds GitHub's dependency graph, so Dependabot can raise actionable security alerts):

```shell
pip3 install -r requirements.lock.txt -e .
```

Then you can run the script directly like so:

```shell
pvecontrol --help
```

## Contributing

This project use _semantic versioning_ with the [python-semantic-release](https://python-semantic-release.readthedocs.io/en/latest/) toolkit to automate the release process. All commits must follow the [Angular Commit Message Conventions](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-format). Repository `main` branch is also protected to prevent accidental releases. All updates must go through a PR with a review.

---

Made with :heart: by Enix (<http://enix.io>) :monkey: from Paris :fr:.
