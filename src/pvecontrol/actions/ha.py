import logging
import sys
import time

import click
import proxmoxer.core

from pvecontrol.models.cluster import PVECluster
from pvecontrol.models.node import NodeHaState, parse_node_ha_states
from pvecontrol.utils import confirm, parse_pve_version, print_output

# PUT nodes/{node}/maintenance appeared in pve-manager 9.2.33, it runs on the node itself
MAINTENANCE_API_VERSION = (9, 2, 33)

# The HA manager runs a round about every 10 s. Not 5 s: pveproxy closes a keep-alive connection idle for 5 s,
# a request sent at that moment fails with the connection
HA_POLL_INTERVAL = 10
HA_WAIT_TIMEOUT = 900

# States of an HA resource that count as active on its node, as count_active_services() in pve-ha-manager
INACTIVE_SERVICE_STATES = ("stopped", "freeze", "error", "request_start")

COLUMNS = ["node", "ha_state", "lrm_mode", "request_queued", "ha_resources", "other_vms"]


@click.group(name="ha", help="HA manager related commands")
def root():
    pass


def _timeout_option(func):
    return click.option(
        "--timeout",
        type=click.IntRange(min=1),
        default=HA_WAIT_TIMEOUT,
        show_default=True,
        metavar="SECONDS",
        help="Maximum time to wait with --wait",
    )(func)


def _read_manager_status(proxmox):
    try:
        return proxmox.ha_manager_status
    except proxmoxer.core.ResourceException as e:
        logging.error("Cannot read the HA manager status, note that it requires Sys.Audit on /: %s", e)
        sys.exit(1)


def _queued_requests(proxmox):
    """Nodes with a maintenance request not yet read by the CRM, reported since pve-ha-manager 5.2.7"""
    try:
        entries = proxmox.api.cluster.ha.status.current.get()
    except proxmoxer.core.ResourceException as e:
        logging.debug("Cannot read the HA status: %s", e)
        return set()
    return {
        entry.get("node")
        for entry in entries
        if entry.get("type") == "lrm" and int(entry.get("maintenance-request-queued", 0))
    }


def _active_services(manager_status, node):
    """HA resources running on the node or moving to it"""
    return sorted(
        sid
        for sid, service in (manager_status.get("service_status") or {}).items()
        if node in (service.get("node"), service.get("target"))
        and service.get("state") is not None
        and service.get("state") not in INACTIVE_SERVICE_STATES
    )


def _node_services(manager_status, node):
    """Every HA resource on the node or moving to it, whatever its state (frozen while HA is disarmed, stopped...)"""
    return sorted(
        sid
        for sid, service in (manager_status.get("service_status") or {}).items()
        if node in (service.get("node"), service.get("target"))
    )


def _describe_services(manager_status, node):
    """The HA resources active on the node with their state, and their target when they move"""
    service_status = manager_status.get("service_status") or {}
    descriptions = []
    for sid in _active_services(manager_status, node):
        service = service_status[sid]
        if service.get("target") and service["target"] != service.get("node"):
            descriptions.append(f"{sid} ({service['state']} from {service.get('node')} to {service['target']})")
        else:
            descriptions.append(f"{sid} ({service['state']})")
    return ", ".join(descriptions) or "none"


def _node_rows(proxmox):
    status = _read_manager_status(proxmox)
    manager_status = status.get("manager_status") or {}
    lrm_status = status.get("lrm_status") or {}
    states = parse_node_ha_states(status)
    queued = _queued_requests(proxmox) if states else set()
    ha_vmids = {
        int(sid.split(":")[1])
        for sid in (manager_status.get("service_status") or {})
        if sid.split(":")[0] == "vm" and sid.split(":")[1].isdigit()
    }
    rows = {}
    for node in sorted(set(states) | {node.node for node in proxmox.nodes}):
        pvenode = proxmox.find_node(node)
        rows[node] = {
            "node": node,
            "ha_state": states.get(node, NodeHaState.NONE),
            "lrm_mode": (lrm_status.get(node) or {}).get("mode", "-"),
            "request_queued": node in queued,
            "ha_resources": ", ".join(_node_services(manager_status, node)),
            # Not displayed: the HA manager only waits for these ones to leave a node entering maintenance
            "active_resources": _active_services(manager_status, node),
            "other_vms": ", ".join(str(vm.vmid) for vm in pvenode.vms if vm.vmid not in ha_vmids) if pvenode else "",
        }
    return rows, manager_status


def _warn_disarmed(manager_status):
    disarm = manager_status.get("disarm")
    if disarm:
        logging.warning("HA is %s, resources are in %s mode", disarm.get("state", "disarmed"), disarm.get("mode"))


def _is_pending(row):
    """The node is entering or leaving the maintenance mode"""
    if row["request_queued"] or row["ha_state"] == NodeHaState.MAINTENANCE_REQUESTED:
        return True
    if row["ha_state"] == NodeHaState.MAINTENANCE:
        # Still draining, or leaving: the request is lifted, the node waits for its LRM to become active again
        return bool(row["active_resources"]) or row["lrm_mode"] != "maintenance"
    return False


def _is_drained(row):
    return row["ha_state"] == NodeHaState.MAINTENANCE and not row["active_resources"] and not row["request_queued"]


def _is_back_online(row):
    return row["ha_state"] == NodeHaState.ONLINE and not row["request_queued"]


def _wait(proxmox, node, done, timeout):
    """Poll the HA manager until done(row) is true for the node, exit 1 on timeout"""
    deadline = time.monotonic() + timeout
    while True:
        row = _node_rows(proxmox)[0].get(node)
        if row is not None and done(row):
            logging.info("Node %s is in HA state %s", node, row["ha_state"])
            return row
        # The rows were just built from the cached manager status
        services = _describe_services(proxmox.ha_manager_status.get("manager_status") or {}, node)
        state = row["ha_state"] if row else NodeHaState.NONE
        if time.monotonic() >= deadline:
            logging.error(
                "Timeout waiting for node %s, it is still in HA state %s, HA resources left: %s. "
                "The HA manager logs of the nodes (pve-ha-crm, pve-ha-lrm) tell why a resource doesn't move",
                node,
                state,
                services,
            )
            sys.exit(1)
        logging.info("Waiting for node %s, HA state %s, HA resources left: %s", node, state, services)
        time.sleep(HA_POLL_INTERVAL)
        proxmox.refresh()


@root.command(name="status")
@click.argument("node", required=False)
@click.option("-w", "--wait", is_flag=True, help="Wait until the node has entered or left the maintenance mode")
@_timeout_option
@click.pass_context
def ha_status(ctx, node, wait, timeout):
    """Show the state of the nodes in the HA manager

    For each node: its HA state, the mode of its local resource manager (LRM), whether a maintenance request is
    queued, the HA resources on it and the VMs not managed by HA.
    """
    if wait and not node:
        raise click.UsageError("--wait requires a NODE")
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    rows, manager_status = _node_rows(proxmox)
    _warn_disarmed(manager_status)
    if node is not None and node not in rows:
        logging.error("Node %s does not exist", node)
        sys.exit(1)

    if wait:
        if not _is_pending(rows[node]):
            logging.error("Node %s is not entering nor leaving the maintenance mode, nothing to wait for", node)
            sys.exit(1)
        _wait(proxmox, node, lambda row: not _is_pending(row), timeout)
        rows = _node_rows(proxmox)[0]

    selected = [rows[node]] if node else list(rows.values())
    print_output(
        [{key: row[key] for key in COLUMNS} for row in selected], columns=COLUMNS, output=ctx.obj["args"].output
    )


def _manual_command(mode, nodename):
    return f"ha-manager crm-command node-maintenance {mode} {nodename}"


def _check_maintenance_api(proxmox, node, mode):
    """Both the node serving the API and the node in maintenance must know PUT nodes/{node}/maintenance:
    the first one refuses a method it doesn't know (HTTP 501) instead of proxying it to the second one,
    which runs the ha-manager command"""
    for role, version in [
        ("the node serving the API", proxmox.version.get("version", "0")),
        (f"node {node.node}", node.version.get("version", "0")),
    ]:
        if parse_pve_version(version) < MAINTENANCE_API_VERSION:
            logging.error(
                "The maintenance API requires pve-manager 9.2.33 or later, %s runs %s. "
                "Run this command on a node instead: %s",
                role,
                version,
                _manual_command(mode, node.node),
            )
            sys.exit(1)


def _check_can_enter_maintenance(proxmox, node):
    """Refuse what the HA manager would refuse: Proxmox VE only returns the first line of the error of the ha-manager
    command, which can be an unrelated warning"""
    disarm = (_read_manager_status(proxmox).get("manager_status") or {}).get("disarm")
    if disarm:
        logging.error("HA is %s, no node can enter the maintenance mode: run ha arm first", disarm.get("state"))
        sys.exit(1)
    if node.ha_state == NodeHaState.NONE:
        logging.error("Node %s is not tracked by the HA manager, it can't enter the maintenance mode", node.node)
        sys.exit(1)
    if node.ha_state in (NodeHaState.UNKNOWN, NodeHaState.FENCE, NodeHaState.GONE):
        logging.error("Node %s is in HA state %s, it can't enter the maintenance mode", node.node, node.ha_state)
        sys.exit(1)


def _set_maintenance(ctx, nodename, mode, force):
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    node = proxmox.find_node(nodename)
    if not node:
        logging.error("Node %s does not exist", nodename)
        sys.exit(1)
    # The request is run by the node itself, through the ha-manager command
    if not node.online:
        logging.error("Node %s is not online, its maintenance mode can't be changed through the API", nodename)
        sys.exit(1)
    _check_maintenance_api(proxmox, node, mode)
    if mode == "enable":
        _check_can_enter_maintenance(proxmox, node)

    print(f"{mode.capitalize()} the HA maintenance mode of node {nodename} (HA state {node.ha_state})")
    if not confirm(force):
        sys.exit(1)
    try:
        proxmox.api.nodes(nodename).maintenance.put(**{"maintenance-mode": mode})
    except proxmoxer.core.ResourceException as e:
        if e.status_code == 501:
            # Behind a load balancer, the node that answered may not be the one that served the version
            logging.error(
                "The node serving the API doesn't know the maintenance API, it requires pve-manager 9.2.33 or later: "
                "%s. Run this command on a node instead: %s",
                e,
                _manual_command(mode, nodename),
            )
        elif e.status_code == 403:
            logging.error(
                "Cannot %s the maintenance mode of node %s, note that it requires Sys.Modify on /: %s",
                mode,
                nodename,
                e,
            )
        else:
            logging.error(
                "Cannot %s the maintenance mode of node %s: %s. Proxmox VE only returns the first line of the error of "
                "the ha-manager command, run it on the node to see it all: %s",
                mode,
                nodename,
                e,
                _manual_command(mode, nodename),
            )
        sys.exit(1)
    print(f"Maintenance mode {mode} requested for node {nodename}")
    return proxmox


@root.command(name="maintenance-enable")
@click.argument("node", required=True)
@click.option("-w", "--wait", is_flag=True, help="Wait until the HA resources have left the node")
@_timeout_option
@click.option("--force", is_flag=True, help="Do not ask for confirmation")
@click.pass_context
def maintenance_enable(ctx, node, wait, timeout, force):
    """Put a node in HA maintenance mode

    The HA manager migrates the HA resources away from the node and doesn't place any on it until the maintenance
    mode is disabled. VMs not managed by HA stay on the node: use node evacuate to move them. Requires
    pve-manager 9.2.33 or later on the node.
    """
    proxmox = _set_maintenance(ctx, node, "enable", force)
    if wait:
        proxmox.refresh()
        row = _wait(proxmox, node, _is_drained, timeout)
    else:
        row = _node_rows(proxmox)[0][node]
    if row["other_vms"]:
        logging.warning(
            "VM(s) not managed by HA stay on node %s: %s, use node evacuate to move them", node, row["other_vms"]
        )


@root.command(name="maintenance-disable")
@click.argument("node", required=True)
@click.option("-w", "--wait", is_flag=True, help="Wait until the node has left the maintenance mode")
@_timeout_option
@click.option("--force", is_flag=True, help="Do not ask for confirmation")
@click.pass_context
def maintenance_disable(ctx, node, wait, timeout, force):
    """Take a node out of HA maintenance mode

    The HA resources that ran on the node before the maintenance move back to it. Requires pve-manager 9.2.33 or
    later on the node.
    """
    proxmox = _set_maintenance(ctx, node, "disable", force)
    if wait:
        proxmox.refresh()
        _wait(proxmox, node, _is_back_online, timeout)


def _check_disarm_api(proxmox):
    """disarm-ha and arm-ha appeared in pve-ha-manager 5.1.3"""
    try:
        names = {entry.get("name") for entry in proxmox.api.cluster.ha.status.get()}
    except proxmoxer.core.ResourceException as e:
        logging.error("Cannot read the HA status API: %s", e)
        sys.exit(1)
    if "disarm-ha" not in names:
        logging.error("This Proxmox VE version can't disarm HA, it requires pve-ha-manager 5.1.3 (PVE 9.1) or later")
        sys.exit(1)


def _post_ha_command(proxmox, command, **params):
    try:
        proxmox.api.cluster.ha.status(command).post(**params)
    except proxmoxer.core.ResourceException as e:
        logging.error("Cannot run %s, note that it requires Sys.Console on /: %s", command, e)
        sys.exit(1)


def _wait_disarm_state(proxmox, done, timeout):
    """Poll the HA manager until done(disarm) is true, disarm being None when HA is armed. Exit 1 on timeout"""
    deadline = time.monotonic() + timeout
    while True:
        proxmox.refresh()
        disarm = (_read_manager_status(proxmox).get("manager_status") or {}).get("disarm")
        if done(disarm):
            return
        if time.monotonic() >= deadline:
            logging.error("Timeout waiting for the HA manager, HA is %s", disarm.get("state") if disarm else "armed")
            sys.exit(1)
        logging.info("Waiting for the HA manager, HA is %s", disarm.get("state") if disarm else "armed")
        time.sleep(HA_POLL_INTERVAL)


@root.command(name="disarm")
@click.option(
    "--mode",
    "resource_mode",
    type=click.Choice(["freeze", "ignore"]),
    required=True,
    help="freeze: HA resources keep their state, new commands are not applied. "
    "ignore: HA resources are not tracked, they can be managed as if HA didn't manage them",
)
@click.option("-w", "--wait", is_flag=True, help="Wait until every node has released its watchdog")
@_timeout_option
@click.option("--force", is_flag=True, help="Do not ask for confirmation")
@click.pass_context
def ha_disarm(ctx, resource_mode, wait, timeout, force):
    """Disarm HA on the whole cluster

    Every node releases its watchdog: no node is fenced, for instance during a network or corosync maintenance.
    No node can enter the maintenance mode while HA is disarmed. Requires Proxmox VE 9.1 or later.
    """
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    _check_disarm_api(proxmox)
    print(f"Disarm HA on cluster {proxmox.cluster_name}, HA resources in {resource_mode} mode")
    if not confirm(force):
        sys.exit(1)
    _post_ha_command(proxmox, "disarm-ha", **{"resource-mode": resource_mode})
    print("HA disarm requested")
    if wait:
        _wait_disarm_state(proxmox, lambda disarm: disarm is not None and disarm.get("state") == "disarmed", timeout)
        print("HA is disarmed")


@root.command(name="arm")
@click.option("-w", "--wait", is_flag=True, help="Wait until HA is armed again")
@_timeout_option
@click.option("--force", is_flag=True, help="Do not ask for confirmation")
@click.pass_context
def ha_arm(ctx, wait, timeout, force):
    """Arm HA again after it was disarmed

    Requires Proxmox VE 9.1 or later.
    """
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    _check_disarm_api(proxmox)
    print(f"Arm HA on cluster {proxmox.cluster_name}")
    if not confirm(force):
        sys.exit(1)
    _post_ha_command(proxmox, "arm-ha")
    print("HA arm requested")
    if wait:
        _wait_disarm_state(proxmox, lambda disarm: disarm is None, timeout)
        print("HA is armed")
