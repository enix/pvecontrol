Proxmox VE Control
===

![release workflow](https://github.com/enix/pvecontrol/actions/workflows/release.yml/badge.svg?branch=main)
![pypi release](https://img.shields.io/pypi/v/pvecontrol.svg)
![pypi downloads](https://img.shields.io/pypi/dm/pvecontrol.svg)

`pvecontrol` (https://pypi.org/project/pvecontrol/) software allows you to manage a Proxmox VE cluster using it's API with a convenient cli for you shell.

It is designed to easy usage of multiple large clusters and get some detailled informations not easily available on the UI and integrated tools.

`pvecontrol` is based upon [proxmoxer](https://pypi.org/project/proxmoxer/) a wonderfull framework to communicate with Proxmox projects APIs.

Installation
---

The software need Python version 3.7+.

The easiest way to install it is simply using pip. New versions are automatically published to [pypi](https://pypi.org/project/pvecontrol/) repository. It is recommended to use `pipx` in order to automatically create a dedicated python virtualenv.

```shell
pipx install pvecontrol
```

Configuration
---

Configuration is a yaml file in `$HOME/.config/pvecontrol/config.yaml`. It contains configuration needed by proxmoxer to connect to a cluster. `pvecontrol` curently only use the http API and so work with an pve realm user or token (and also a `@pam` user but is not recommended at all).

It is highly recommended to setup a dedicated user for the tool usage. You should not use `root@pam` proxmox node credentials in any ways for production systems because the configuration file is stored in plain text without ciphering on your system.

If you plan to use `pvecontrol` in read only mode to fetch cluster informations you can limit user with only `PVEAuditor` on Path `/` Permissions. This is the minimum permissions needed by `pvecontrol` to work.
For other operations on VMs it is recommended to grant `PVEVMAdmin` on Path `/`. This allows start, stop, migrate, ...

Once you have setup your management user for `pvecontrol` you can generate your configuration file. Default configuration template with all options is available (here)[https://github.com/enix/pvecontrol/blob/dev/src/pvecontrol/config_default.yaml]. Use this file to build your own configuration file or the above exemple:
```yaml
---

clusters:
- name: my-test-cluster
    host: 192.168.1.10
    user: pvecontrol@pve
    password: superpasssecret
- name: prod-cluster-1
    host: 10.10.10.10
    user: pvecontrol@pve
    password: Supers3cUre
node:
  # Overcommit cpu factor. can be 1 for not overcommit
  cpufactor: 2.5
  # Memory to reserve for system on a node. in Bytes
  memoryminimum: 81928589934592

```

Usage
---

`pvecontrol` provide a complete *help* message for quick usage:

```shell
$ pvecontrol --help
usage: pvecontrol [-h] [-v] [--debug] -c CLUSTER {clusterstatus,nodelist,vmlist,tasklist,taskget} ...

Proxmox VE control cli.

positional arguments:
  {clusterstatus,nodelist,vmlist,tasklist,taskget}
                        sub-command help
    clusterstatus       Show cluster status
    nodelist            List nodes in the cluster
    vmlist              List VMs in the cluster
    tasklist            List tasks
    taskget             Get task detail

options:
  -h, --help            show this help message and exit
  -v, --verbose
  --debug
  -c CLUSTER, --cluster CLUSTER
                        Proxmox cluster name as defined in configuration
```

`pvecontrol` works with subcommands for each operation. Each subcommand have it's own *help*:

```shell
$ pvecontrol taskget --help
usage: pvecontrol taskget [-h] --upid UPID [-f]

options:
  -h, --help    show this help message and exit
  --upid UPID   Proxmox tasks UPID to get informations
  -f, --follow  Follow task log output

```

For each operation it is mandatory to tell `pvecontrol` on which cluster from your configuration file you want to operate. So the `--cluster` argument is mandatory.

The simpliest operation on a cluster that allows to check that user is correctly configured is `clusterstatus`:

```shell
$ pvecontrol --cluster my-test-cluster clusterstatus
INFO:root:Proxmox cluster: my-test-cluster
INFO:root:{'nodes': 9, 'id': 'cluster', 'type': 'cluster', 'quorate': 1, 'version': 17, 'name': 'pve-r1az2'}
+-----------+-------+---------+--------------+--------------+
| name      | nodes | quorate | allocatedmem | allocatedcpu |
+-----------+-------+---------+--------------+--------------+
| pve-r1az2 | 9     | 1       | 583.5 GiB    | 167          |
+-----------+-------+---------+--------------+--------------+
```

If this works, you're ready to go

Development
---

Install python requirements and directly use the script. All the configurations are common with the standard installation.

```shell
pip3 install -r requirements.txt
python3 src/pvecontrol/pvecontrol.py -h
```

This project use *semantic versioning* with [python-semantic-release](https://python-semantic-release.readthedocs.io/en/latest/) toolkit in order to automate release process. All the commits must so use the [Angular Commit Message Conventions](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-format). Repository `main` branch is also protected to prevent any unwanted publish of a new release. All updates must go thru a PR with a review.

---

Made with :heart: by Enix (http://enix.io) :monkey: from Paris :fr:.
