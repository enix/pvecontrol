# Proxmox VE Control

![release workflow](https://github.com/enix/pvecontrol/actions/workflows/release.yml/badge.svg?branch=main)
![pypi release](https://img.shields.io/pypi/v/pvecontrol.svg)
![pypi downloads](https://img.shields.io/pypi/dm/pvecontrol.svg)

`pvecontrol` (<https://pypi.org/project/pvecontrol/>) is a CLI tool to manage Proxmox VE clusters and perform intermediate and advanced tasks that aren't available (or aren't straightforward) in the Proxmox web UI or default CLI tools.

It was written by (and for) teams managing multiple Proxmox clusters, sometimes with many hypervisors. Conversely, if your Proxmox install consists of a single cluster with a single node, the features of `pvecontrol` might not be very interesting for you!

Here are a few examples of things you can do with `pvecontrol`:

- List all VMs across all hypervisors, along with their state and size;
- Evacuate (=drain) a hypervisor, i.e. migrate all VMs that are running on that hypervisor, automatically picking nodes with enough capacity to host these VMs.

To communicate with Proxmox VE, `pvecontrol` uses [proxmoxer](https://pypi.org/project/proxmoxer/), a wonderful library that enables communication with various Proxmox APIs.

## Installation

`pvecontrol` requires Python version 3.7 or above.

The easiest way to install it is simply using pip. New versions are automatically published to [pypi](https://pypi.org/project/pvecontrol/) repository. It is recommended to use `pipx` in order to automatically create a dedicated python virtual environment:

```shell
pipx install pvecontrol
```

## Configuration

To use `pvecontrol`, you must create a YAML configuration in `$HOME/.config/pvecontrol/config.yaml`. That file will list your clusters and how to authenticate with them.

`pvecontrol` only uses the Proxmox HTTP API, which means that you can use most Proxmox authentication mechanisms, including `@pve` realm users and tokens.

As an example, here's how to set up a dedicated user for `pvecontrol`, with read-only access to the Proxmox API:

```shell
pveum user add pvecontrol@pve --password my.password.is.weak
pveum acl modify / --roles PVEAuditor --users pvecontrol@pve
```

You can then create the following configuration file in `$HOME/.config/pvecontrol/config.yaml`:

```yaml
clusters:
  - name: fr-par-1
    host: localhost
    user: pvecontrol@pve
    password: my.password.is.weak
```

And see `pvecontrol` in action right away:

```shell
pvecontrol -c fr-par-1 vmlist
```

If you plan to use `pvecontrol` to move VMs around, you should grant it `PVEVMAdmin` permissions:

```shell
pveum acl modify / --roles PVEVMAdmin --users pvecontrol@pve
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

### Reverse proxies

`pvecontrol` supports certificate-based authentication to a reverse proxy. Which makes it suitable for use with tools like [teleport](https://goteleport.com/docs/enroll-resources/application-access/guides/connecting-apps/) using teleport apps.

```yaml
clusters:
  - name: fr-par-1
    host: localhost
    user: pvecontrol@pve
    password: my.password.is.weak
    proxy_certificate_path: /tmp/proxmox-reverse-proxy.pem
    proxy_certificate_key_path: /tmp/proxmox-reverse-proxy
```

You can also use command substitution syntax and the key `proxy_certificate` to execute a command that will output a json containing the certficate and key paths.

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

CAUTION: environment variable and `~` expansion and are not supported.

### Better security

Instead of specifying users, passwords and certificates paths in plain text in the configuration file, you can use the shell command substitution syntax `$(...)` inside the `user`, `password`, `proxy_certificate` fields; for instance:

```yaml
clusters:
  - name: prod-cluster-1
    host: 10.10.10.10
    user: pvecontrol@pve
    password: $(command to get -password)
```

### Worse security

You _can_ use `@pam` users (and even `root@pam`) and passwords in the `pvecontrol` YAML configuration file; but you probably _should not_, as anyone with read access to the configuration file would then automatically gain shell access to your Proxmox hypervisor. _Not recommended in production!_

### Advanced configuration options

The configuration file can include a `node:` section to specify CPU and memory policies. These will be used when scheduling a VM (i.e. determine on which node it should run), specifically when draining a node for maintenance.

There are currently two parameters: `cpufactor` and `memoryminimum`.

`cpufactor` indicates the level of overcommit allowed on a hypervisor. `1` means no overcommit at all; `5` means "a hypervisor with 8 cores can run VMs with up to 5x8 = 40 cores in total".

`memoryminimum` is the amount of memory that should always be available on a node, in bytes. When scheduling a VM (for instance, when automatically moving VMs around), `pvecontrol` will make sure that this amount of memory remains available for the hypervisor OS itself. Caution: if that amount is set to zero, it will be possible to allocate the entire host memory to virtual machines, leaving no memory for the hypervisor operating system and management daemons!

These options can be specified in a global `node:` section, and then overridden per cluster.

Here is a configuration file showing this in action:

```yaml
---
node:
  # Overcommit CPU factor
  # 1 = no overcommit
  cpufactor: 2.5
  # Memory to reserve for the system on a node (in bytes)
  memoryminimum: 8589934592
clusters:
- name: my-test-cluster
    host: 192.168.1.10
    user: pvecontrol@pve
    password: superpasssecret
    # Override global values for this cluster
    node:
      cpufactor: 1
- name: prod-cluster-1
    host: 10.10.10.10
    user: pvecontrol@pve
    password: Supers3cUre
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

## Usage

Here is a quick overview of `pvecontrol` commands and options:

```shell
$ pvecontrol --help
usage: pvecontrol [-h] [-v] [--debug] [-o {text,json,csv,yaml}] -c CLUSTER
               [-s {bash,zsh,tcsh}]
               {clusterstatus,storagelist,nodelist,nodeevacuate,vmlist,vmmigrate,tasklist,taskget,sanitycheck,_test} ...

Proxmox VE control cli.

positional arguments:
  {clusterstatus,storagelist,nodelist,nodeevacuate,vmlist,vmmigrate,tasklist,taskget,sanitycheck,_test}
    clusterstatus       Show cluster status
    storagelist         Show cluster status
    nodelist            List nodes in the cluster
    nodeevacuate        Evacuate an host by migrating all VMs
    vmlist              List VMs in the cluster
    vmmigrate           Migrate VMs in the cluster
    tasklist            List tasks
    taskget             Get task detail
    sanitycheck         Run Sanity checks on the cluster

options:
  -h, --help            show this help message and exit
  -v, --verbose
  --debug
  -o, --output {text,json,csv,yaml}
  -c, --cluster CLUSTER
                        Proxmox cluster name as defined in configuration
  -s, --print-completion {bash,zsh,tcsh}
                        print shell completion script
```

`pvecontrol` works with subcommands for each operation. Each subcommand has its own help:

```shell
$ pvecontrol taskget --help
usage: pvecontrol taskget [-h] --upid UPID [-f]

options:
  -h, --help    show this help message and exit
  --upid UPID   Proxmox tasks UPID to get informations
  -f, --follow  Follow task log output
```

Commands that communicate with Proxmox (such as `nodelist` or `vmlist`) require that we specify the `-c` or `--cluster` flag to indicate on which cluster we want to work.

The simplest operation we can do to check that `pvecontrol` works correctly, and that authentication has been configured properly is `clusterstatus`:

```shell
$ pvecontrol --cluster my-test-cluster clusterstatus
INFO:root:Proxmox cluster: my-test-cluster

  Status: healthy
  VMs: 0
  Templates: 0
  Metrics:
    CPU: 0.00/64(0.0%), allocated: 0
    Memory: 0.00 GiB/128.00 GiB(0.0%), allocated: 0.00 GiB
    Disk: 0.00 GiB/2.66 TiB(0.0%)
  Nodes:
    Offline: 0
    Online: 3
    Unknown: 0
```

If this works, we're good to go!

## Shell completion

`pvecontrol` provides a completion helper to generate completion configuration for common shells. It currently supports `bash`, `tcsh`, and `zsh`.

You can adapt the following commands to your environment:

```shell
# bash
pvecontrol --print-completion bash > "${BASH_COMPLETION_USER_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion}/completions/pvecontrol"
# zsh
pvecontrol --print-completion zsh > "${HOME}/.zsh/completions/_pvecontrol"
```

## Development

If you want to tinker with the code, all the required dependencies are listed in `requirements.txt`, and you can install them e.g. with pip:

```shell
pip3 install -r requirements.txt
pip3 install -e .
```

Then you can run the script directly like so:

```shell
python3 src/main.py -h
```

## Contributing

This project use _semantic versioning_ with the [python-semantic-release](https://python-semantic-release.readthedocs.io/en/latest/) toolkit to automate the release process. All commits must follow the [Angular Commit Message Conventions](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-format). Repository `main` branch is also protected to prevent accidental releases. All updates must go through a PR with a review.

---

Made with :heart: by Enix (<http://enix.io>) :monkey: from Paris :fr:.
