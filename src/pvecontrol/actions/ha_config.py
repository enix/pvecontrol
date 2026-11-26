"""Commands of the ha group that edit the HA configuration: the HA resources and the HA rules"""

import logging
import sys

import click
import proxmoxer.core

from pvecontrol.actions.ha import root
from pvecontrol.cli import add_list_resource_command
from pvecontrol.models.cluster import PVECluster
from pvecontrol.models.ha import RESOURCE_COLUMNS, RULE_COLUMNS, PVEHaRule, format_api_errors, rule_conflicts, sid_vmid
from pvecontrol.utils import confirm

# "enabled" is an alias of "started" in the API
RESOURCE_STATES = ["started", "stopped", "disabled", "ignored"]
RULE_TYPES = ["node-affinity", "resource-affinity"]
AFFINITIES = ["positive", "negative"]


def _api_error(message, e):
    """Log an error of the HA API with its details per option, when it gives them"""
    details = format_api_errors(e.errors)
    reason = e.content.strip() if isinstance(e.content, str) else ""
    if not details and "is invalid" in reason:
        # The API checks the rule against the others, but loses the reason on the way
        details = "(Proxmox VE doesn't return why: see the feasibility checks of HA rules in its documentation)"
    logging.error("%s: %s %s%s", message, e.status_code, reason, f" {details}" if details else "")


def _list_or_exit(callback, what):
    def _(proxmox):
        try:
            return callback(proxmox)
        except proxmoxer.core.ResourceException as e:
            _api_error(f"Cannot read the {what}, note that it requires Sys.Audit on /", e)
            sys.exit(1)

    return _


def _ha_resources(proxmox):
    try:
        return {resource.vmid: resource for resource in proxmox.ha_resources}
    except proxmoxer.core.ResourceException as e:
        _api_error("Cannot read the HA resources, note that it requires Sys.Audit on /", e)
        sys.exit(1)


def _ha_rules(proxmox):
    try:
        return {rule.rule: rule for rule in proxmox.ha_rules}
    except proxmoxer.core.ResourceException as e:
        _api_error("Cannot read the HA rules (Proxmox VE 9.0 or later), note that it requires Sys.Audit on /", e)
        sys.exit(1)


def _describe(params):
    return ", ".join(f"{key}={value}" for key, value in params.items()) or "no change"


# HA resources

add_list_resource_command(
    "HA resource",
    root,
    RESOURCE_COLUMNS,
    "vmid",
    _list_or_exit(lambda proxmox: proxmox.ha_resources, "HA resources"),
    command_name="resource-list",
)


def _resource_options(func):
    for decorator in reversed(
        [
            click.option(
                "--state",
                type=click.Choice(RESOURCE_STATES),
                help="State requested to the HA manager [API default: started]",
            ),
            click.option(
                "--max-restart",
                type=click.IntRange(min=0),
                help="Restarts on the same node after a failed start [API default: 1]",
            ),
            click.option(
                "--max-relocate",
                type=click.IntRange(min=0),
                help="Relocations to another node after the restarts failed [API default: 1]",
            ),
            click.option(
                "--failback/--no-failback",
                default=None,
                help="Move back to the node with the highest priority of its node affinity rule [API default: on]",
            ),
            click.option(
                "--auto-rebalance/--no-auto-rebalance",
                default=None,
                help="Let the CRS auto-rebalancer move the VM, Proxmox VE 9.2 [API default: on]",
            ),
            click.option("--comment", help="Comment, an empty one deletes it"),
            click.option("--force", is_flag=True, help="Do not ask for confirmation"),
        ]
    ):
        func = decorator(func)
    return func


def _resource_params(state, max_restart, max_relocate, failback, auto_rebalance, comment, creating):
    params = {
        "state": state,
        "max_restart": max_restart,
        "max_relocate": max_relocate,
        "failback": failback,
        "auto-rebalance": auto_rebalance,
    }
    params = {
        key: int(value) if isinstance(value, bool) else value for key, value in params.items() if value is not None
    }
    if comment:
        params["comment"] = comment
    elif comment is not None and not creating:
        params["delete"] = "comment"
    return params


def _run_writes(writes, action):
    """Run the API calls, (label, call) pairs, and exit 1 once they are all tried when any failed"""
    failed = False
    for label, call in writes:
        try:
            call()
        except proxmoxer.core.ResourceException as e:
            _api_error(f"Cannot {action} {label}", e)
            failed = True
        else:
            print(f"{action[0].upper()}{action[1:]} {label}: done")
    if failed:
        sys.exit(1)


def _check_new_resources(proxmox, vmids, resources):
    """Every VM exists, is not a template nor already an HA resource, checked before any write"""
    errors = []
    for vmid in vmids:
        vm = proxmox.get_vm(vmid)
        if vm is None:
            errors.append(f"VM {vmid} does not exist")
        elif vm.template:
            errors.append(f"VM {vmid} is a template")
        elif vmid in resources:
            errors.append(f"VM {vmid} is already an HA resource, use ha resource-set to change it")
    if errors:
        for error in errors:
            logging.error(error)
        sys.exit(1)


@root.command(name="resource-add")
@click.argument("vmids", metavar="VMID...", nargs=-1, required=True, type=int)
@_resource_options
@click.pass_context
def resource_add(ctx, vmids, state, max_restart, max_relocate, failback, auto_rebalance, comment, force):
    """Add VMs to HA, as HA resources

    The HA manager then starts them, unless --state says otherwise, restarts them when they fail and recovers them on
    another node when theirs fails. Options not given keep the default of the API. Requires Sys.Console on /.
    """
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    resources = _ha_resources(proxmox)
    params = _resource_params(state, max_restart, max_relocate, failback, auto_rebalance, comment, creating=True)
    _check_new_resources(proxmox, vmids, resources)

    for vmid in vmids:
        vm = proxmox.get_vm(vmid)
        print(
            f"Add VM {vmid} ({vm.name}, {vm.status} on {vm.node}) to HA: {_describe(params) if params else 'default settings'}"
        )
    if not confirm(force):
        sys.exit(1)
    _run_writes(
        [
            (f"vm:{vmid}", lambda vmid=vmid: proxmox.api.cluster.ha.resources.post(sid=f"vm:{vmid}", **params))
            for vmid in vmids
        ],
        "add HA resource",
    )


@root.command(name="resource-set")
@click.argument("vmids", metavar="VMID...", nargs=-1, required=True, type=int)
@_resource_options
@click.pass_context
def resource_set(ctx, vmids, state, max_restart, max_relocate, failback, auto_rebalance, comment, force):
    """Change the HA parameters of HA resources

    Only the options given are changed. A state of stopped or disabled makes the HA manager stop the VMs. Requires
    Sys.Console on /.
    """
    params = _resource_params(state, max_restart, max_relocate, failback, auto_rebalance, comment, creating=False)
    if not params:
        raise click.UsageError("Nothing to change, give at least one option")

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    resources = _ha_resources(proxmox)
    missing = [vmid for vmid in vmids if vmid not in resources]
    if missing:
        logging.error(
            "VM(s) %s are not HA resources, add them with ha resource-add", ", ".join(str(vmid) for vmid in missing)
        )
        sys.exit(1)

    for vmid in vmids:
        resource = resources[vmid]
        print(f"Set HA resource vm:{vmid} ({resource.name}, {resource.state}): {_describe(params)}")
    if state in ("stopped", "disabled"):
        logging.warning("The HA manager stops the VM(s) in state %s", state)
    if not confirm(force):
        sys.exit(1)
    _run_writes(
        [
            (f"vm:{vmid}", lambda vmid=vmid: proxmox.api.cluster.ha.resources(f"vm:{vmid}").put(**params))
            for vmid in vmids
        ],
        "set HA resource",
    )


@root.command(name="resource-remove")
@click.argument("vmids", metavar="VMID...", nargs=-1, required=True, type=int)
@click.option(
    "--purge/--no-purge",
    default=True,
    show_default=True,
    help="Also remove the VMs from the HA rules, and delete the rules left without resource",
)
@click.option("--force", is_flag=True, help="Do not ask for confirmation")
@click.pass_context
def resource_remove(ctx, vmids, purge, force):
    """Remove VMs from HA

    The VMs keep running, or stay stopped, but the HA manager doesn't manage them anymore. Requires Sys.Console on /.
    """
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    resources = _ha_resources(proxmox)
    missing = [vmid for vmid in vmids if vmid not in resources]
    if missing:
        logging.error("VM(s) %s are not HA resources", ", ".join(str(vmid) for vmid in missing))
        sys.exit(1)

    sids = {f"vm:{vmid}" for vmid in vmids}
    for vmid in vmids:
        resource = resources[vmid]
        print(f"Remove HA resource vm:{vmid} ({resource.name}, rules: {resource.rules or 'none'})")
    rules = [rule for rule in _ha_rules(proxmox).values() if sids & set(rule.sids)] if purge else []
    for rule in rules:
        if set(rule.sids) <= sids:
            print(f"Delete HA rule {rule.rule}, it has no resource left")
        else:
            print(f"Remove {', '.join(sorted(sids & set(rule.sids)))} from HA rule {rule.rule}")
    if not confirm(force):
        sys.exit(1)
    _run_writes(
        [
            (sid, lambda sid=sid: proxmox.api.cluster.ha.resources(sid).delete(purge=int(purge)))
            for sid in sorted(sids, key=sid_vmid)
        ],
        "remove HA resource",
    )


# HA rules

add_list_resource_command(
    "HA rule",
    root,
    RULE_COLUMNS,
    "rule",
    _list_or_exit(lambda proxmox: proxmox.ha_rules, "HA rules (Proxmox VE 9.0 or later)"),
    command_name="rule-list",
)


def _parse_resources(value):
    """VMIDs given as 100,101 (or vm:100,vm:101) to the "vm:100,vm:101" of the API"""
    sids = []
    for item in filter(None, (item.strip() for item in value.split(","))):
        vmid = sid_vmid(item) if item.startswith("vm:") else (int(item) if item.isdigit() else None)
        if vmid is None:
            raise click.BadParameter(f"{item} is not a VMID", param_hint="--resources")
        sids.append(f"vm:{vmid}")
    if not sids:
        raise click.BadParameter("no VMID given", param_hint="--resources")
    return ",".join(sids)


def _check_rule_conflicts(proxmox, rule, rules):
    conflicts = rule_conflicts(rule, rules.values(), [node.node for node in proxmox.nodes])
    if conflicts:
        for conflict in conflicts:
            logging.error("HA rule %s is not valid: %s", rule.rule, conflict)
        sys.exit(1)


def _check_rule_targets(proxmox, resources, nodes):
    """The API refuses a rule naming a VM that is not an HA resource, or a node that doesn't exist"""
    errors = []
    if resources:
        ha_vmids = set(_ha_resources(proxmox))
        missing = [sid for sid in resources.split(",") if sid_vmid(sid) not in ha_vmids]
        if missing:
            errors.append(f"{', '.join(missing)} are not HA resources, add them with ha resource-add first")
    if nodes:
        names = {node.node for node in proxmox.nodes}
        unknown = [item.split(":")[0] for item in nodes.split(",") if item.split(":")[0] not in names]
        if unknown:
            errors.append(f"Node(s) {', '.join(unknown)} do not exist")
    if errors:
        for error in errors:
            logging.error(error)
        sys.exit(1)


def _rule_options(func):
    for decorator in reversed(
        [
            click.option(
                "--resources",
                metavar="VMIDS",
                callback=lambda ctx, param, value: None if value is None else _parse_resources(value),
                help="Comma-separated VMIDs of HA resources",
            ),
            click.option(
                "--nodes",
                metavar="NODE[:PRIORITY],...",
                help="node-affinity only: the nodes, with an optional priority (the higher, the more preferred)",
            ),
            click.option(
                "--affinity",
                type=click.Choice(AFFINITIES),
                help="node-affinity: run on the nodes (positive, default) or away from them (negative). "
                "resource-affinity, required: keep the resources together (positive) or apart (negative)",
            ),
            click.option(
                "--strict/--no-strict",
                default=None,
                help="node-affinity only: the resources only run on the nodes, they stop when none is available "
                "[API default: no-strict]",
            ),
            click.option("--comment", help="Comment, an empty one deletes it"),
            click.option("--force", is_flag=True, help="Do not ask for confirmation"),
        ]
    ):
        func = decorator(func)
    return func


def _check_rule_type(rule_type, nodes, affinity, strict, creating):
    if rule_type == "resource-affinity":
        if nodes is not None or strict is not None:
            raise click.UsageError("--nodes and --strict only apply to node-affinity rules")
        if creating and affinity is None:
            raise click.UsageError("--affinity is required for a resource-affinity rule")
    elif creating and nodes is None:
        raise click.UsageError("--nodes is required for a node-affinity rule")


def _rule_params(resources, nodes, affinity, strict):
    params = {"resources": resources, "nodes": nodes, "affinity": affinity, "strict": strict}
    return {key: int(value) if isinstance(value, bool) else value for key, value in params.items() if value is not None}


@root.command(name="rule-add")
@click.argument("rule")
@click.option("--type", "rule_type", type=click.Choice(RULE_TYPES), required=True, help="Type of the rule")
@_rule_options
@click.option("--disable", is_flag=True, help="Create the rule disabled")
@click.pass_context
def rule_add(ctx, rule, rule_type, resources, nodes, affinity, strict, comment, force, disable):
    """Create an HA rule

    A node-affinity rule keeps HA resources on some nodes, or away from them with --affinity negative. A
    resource-affinity rule keeps HA resources together (--affinity positive) or on separate nodes (--affinity
    negative, anti-affinity). Proxmox VE refuses a rule that conflicts with the others, the error tells why. Requires
    Sys.Console on /.
    """
    if resources is None:
        raise click.UsageError("--resources is required")
    _check_rule_type(rule_type, nodes, affinity, strict, creating=True)
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    rules = _ha_rules(proxmox)
    if rule in rules:
        logging.error("HA rule %s already exists, use ha rule-set to change it", rule)
        sys.exit(1)
    _check_rule_targets(proxmox, resources, nodes)

    params = {"type": rule_type, **_rule_params(resources, nodes, affinity, strict)}
    if comment:
        params["comment"] = comment
    if disable:
        params["disable"] = 1
    _check_rule_conflicts(proxmox, PVEHaRule(rule=rule, **params), rules)
    print(f"Create HA rule {rule}: {_describe(params)}")
    if not confirm(force):
        sys.exit(1)
    _run_writes([(rule, lambda: proxmox.api.cluster.ha.rules.post(rule=rule, **params))], "create HA rule")


@root.command(name="rule-set")
@click.argument("rule")
@_rule_options
@click.option("--enable/--disable", "enable", default=None, help="Enable or disable the rule")
@click.pass_context
def rule_set(ctx, rule, resources, nodes, affinity, strict, comment, force, enable):
    """Change an HA rule

    Only the options given are changed, --resources and --nodes replace the whole list. The type of a rule can't
    change. Proxmox VE refuses a change that makes the rule conflict with the others, the error tells why. Requires
    Sys.Console on /.
    """
    params = _rule_params(resources, nodes, affinity, strict)
    deleted = []
    if comment:
        params["comment"] = comment
    elif comment is not None:
        deleted.append("comment")
    if enable is False:
        params["disable"] = 1
    elif enable:
        deleted.append("disable")
    if deleted:
        params["delete"] = ",".join(deleted)
    if not params:
        raise click.UsageError("Nothing to change, give at least one option")

    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    rules = _ha_rules(proxmox)
    current = rules.get(rule)
    if current is None:
        logging.error("HA rule %s does not exist", rule)
        sys.exit(1)
    _check_rule_type(current.type, nodes, affinity, strict, creating=False)
    _check_rule_targets(proxmox, resources, nodes)
    updated = {
        "rule": rule,
        "type": current.type,
        "resources": resources or current.resources,
        "nodes": current.nodes if nodes is None else nodes,
        "affinity": affinity or current.affinity,
        "disable": current.disable if enable is None else not enable,
    }
    _check_rule_conflicts(proxmox, PVEHaRule(**updated), rules)

    print(f"Set HA rule {rule} ({current.type}): {_describe(params)}")
    if not confirm(force):
        sys.exit(1)
    _run_writes(
        [(rule, lambda: proxmox.api.cluster.ha.rules(rule).put(type=current.type, digest=current.digest, **params))],
        "set HA rule",
    )


@root.command(name="rule-remove")
@click.argument("rule")
@click.option("--force", is_flag=True, help="Do not ask for confirmation")
@click.pass_context
def rule_remove(ctx, rule, force):
    """Delete an HA rule

    Its resources stay HA resources. Requires Sys.Console on /.
    """
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    current = _ha_rules(proxmox).get(rule)
    if current is None:
        logging.error("HA rule %s does not exist", rule)
        sys.exit(1)
    print(f"Delete HA rule {rule} ({current.type}, {current.affinity}, resources {current.resources})")
    if not confirm(force):
        sys.exit(1)
    _run_writes([(rule, lambda: proxmox.api.cluster.ha.rules(rule).delete())], "delete HA rule")
