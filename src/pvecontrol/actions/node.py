import logging
import sys

import click

from pvecontrol.models.node import NodeStatus
from pvecontrol.models.vm import VmStatus, COLUMNS as VM_COLUMNS
from pvecontrol.utils import as_row, confirm, format_row, match_filters, print_task
from pvecontrol.cli import ResourceGroup, filter_option, migration_related_command
from pvecontrol.models.node import COLUMNS
from pvecontrol.models.cluster import PVECluster


@click.group(
    cls=ResourceGroup,
    name="node",
    columns=COLUMNS,
    default_sort="node",
    list_callback=lambda proxmox: proxmox.nodes,
)
def root():
    pass


@root.command()
@click.argument("node", required=True)
@click.argument("target", nargs=-1)
@migration_related_command
@click.option("--no-skip-stopped", is_flag=True, help="Don't skip VMs that are stopped")
@filter_option(
    VM_COLUMNS,
    "--filter",
    "filters",
    help_text="Only evacuate the VMs whose column matches the regex, as vm list --filter (can be set multiple times)",
)
@filter_option(
    VM_COLUMNS,
    "--exclude",
    "excludes",
    help_text="Leave the VMs whose column matches the regex on the node (can be set multiple times)",
)
@click.pass_context
def evacuate(ctx, node, target, dry_run, online, follow, wait, no_skip_stopped, filters, excludes):
    """Evacuate a node by migrating all it's VM out to one or multiple target nodes"""
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    srcnode = _source_node(proxmox, node)
    _evacuate_vms(proxmox, srcnode, target, dry_run, online, follow, wait, no_skip_stopped, filters, excludes)


# Each option of evacuate is an argument, they are most of the locals
# pylint: disable-next=too-many-locals
def _evacuate_vms(proxmox, srcnode, target, dry_run, online, follow, wait, no_skip_stopped, filters, excludes):
    targets = _find_targets(proxmox, srcnode, target)
    vms, need_online = _select_vms(srcnode, filters, excludes, no_skip_stopped, online)
    plan, unplaced = _place(proxmox, vms, targets)

    logging.debug(plan)
    if len(plan) == 0:
        if _log_vms_left(srcnode, unplaced, need_online):
            sys.exit(1)
        logging.info("No VM to migrate")
        return
    for vm, dest in plan:
        print(f"Migrating VM {vm.vmid} ({vm.name}) from {srcnode.node} to {dest.node}")
    if not confirm():
        sys.exit(1)

    failed = []
    for vm, dest in plan:
        print(f"Migrate VM: {vm.vmid} / {vm.name} from {srcnode.node} to {dest.node}")
        if dry_run:
            print("Dry run, skipping migration")
            continue
        upid = vm.migrate(dest.node, online)
        logging.debug("Migration UPID: %s", upid)
        proxmox.refresh()
        task = print_task(proxmox, upid, follow, wait)
        # Without --follow or --wait the task is usually still running and its result is unknown
        if task.failed():
            failed.append(vm)

    if failed:
        logging.error("Migration failed for VM(s): %s", _vmids(failed))
    if _log_vms_left(srcnode, unplaced, need_online) or failed:
        sys.exit(1)


def _source_node(proxmox, nodename):
    srcnode = proxmox.find_node(nodename)
    logging.debug(srcnode)
    if not srcnode:
        logging.error("Node %s does not exist", nodename)
        sys.exit(1)
    if srcnode.status != NodeStatus.ONLINE:
        logging.error("Node %s is not online", nodename)
        sys.exit(1)
    return srcnode


def _find_targets(proxmox, srcnode, patterns):
    targets = []
    if patterns:
        for pattern in set(patterns):
            nodes = proxmox.find_nodes(pattern)
            if not nodes:
                logging.warning("No node match the pattern %s, skipping", pattern)
            for node in nodes:
                if node.node == srcnode.node:
                    logging.warning("Target node %s is the same as source node, skipping", node.node)
                elif node.status != NodeStatus.ONLINE:
                    logging.warning("Target node %s is not online, skipping", node.node)
                elif not node.ha_state.available:
                    logging.warning("Target node %s is in HA state %s, skipping", node.node, node.ha_state)
                else:
                    targets.append(node)
    else:
        targets = [n for n in proxmox.nodes if n.status == NodeStatus.ONLINE and n.node != srcnode.node]
        for unavailable in [n for n in targets if not n.ha_state.available]:
            logging.warning("Node %s is in HA state %s, it is not a target", unavailable.node, unavailable.ha_state)
        targets = [n for n in targets if n.ha_state.available]
    if len(targets) == 0:
        # An empty node needs no target: the VMs that can't be placed are reported once the plan is built
        logging.warning("No target node available")
    # Make sure there is no duplicate in targets
    targets = list(set(targets))
    logging.debug("Migration targets: %s", ([t.node for t in targets]))
    return targets


def _select_vms(srcnode, filters, excludes, no_skip_stopped, online):
    """The VMs to migrate, and the running ones that need --online"""
    vms = []
    need_online = []
    for vm in srcnode.vms:
        if vm.status != VmStatus.RUNNING and not no_skip_stopped:
            logging.debug("VM %i is not running, skipping", vm.vmid)
            continue
        # An excluded VM is left on purpose: it doesn't need --online
        if not _vm_selected(vm, filters, excludes):
            logging.info("VM %s (%s) is excluded by --filter / --exclude, skipping", vm.vmid, vm.name)
            continue
        # PVE refuses to migrate a running VM offline
        if vm.status == VmStatus.RUNNING and not online:
            logging.warning("VM %s (%s) is running, use --online to migrate it, skipping", vm.vmid, vm.name)
            need_online.append(vm)
            continue
        vms.append(vm)
    return vms, need_online


def _place(proxmox, vms, targets):
    """Greedy placement, in VM order, against the allocations of the targets it updates: (vm, target) pairs and the
    VMs that fit nowhere"""
    memoryminimum = proxmox.config["node"]["memoryminimum"]
    cpufactor = proxmox.config["node"]["cpufactor"]
    plan = []
    unplaced = []
    for vm in vms:
        logging.debug("Selecting node for VM: %i, maxmem: %i, cpus: %i", vm.vmid, vm.maxmem, vm.cpus)
        for dest in targets:
            logging.debug(
                "Test target: %s, allocatedmem: %i, allocatedcpu: %i", dest.node, dest.allocatedmem, dest.allocatedcpu
            )
            if (vm.maxmem + dest.allocatedmem) > (dest.maxmem - memoryminimum):
                logging.debug("Discard target: %s, will overcommit ram", dest.node)
            elif (vm.cpus + dest.allocatedcpu) > (dest.maxcpu * cpufactor):
                logging.debug("Discard target: %s, will overcommit cpu", dest.node)
            else:
                plan.append((vm, dest))
                dest.allocatedmem += vm.maxmem
                dest.allocatedcpu += vm.cpus
                logging.debug(
                    "Selected target %s: new allocatedmem %i, new allocatedcpu %i",
                    dest.node,
                    dest.allocatedmem,
                    dest.allocatedcpu,
                )
                break
        else:
            logging.warning("No target found for VM %s (%s), skipping", vm.vmid, vm.name)
            unplaced.append(vm)
    return plan, unplaced


def _vm_selected(vm, filters, excludes):
    """Tell whether a VM matches every --filter and no --exclude, on the values vm list displays"""
    row = format_row(as_row(vm, VM_COLUMNS))
    return match_filters(row, filters) and not any(match_filters(row, [exclude]) for exclude in excludes)


def _vmids(vms):
    return ", ".join(str(vm.vmid) for vm in vms)


def _log_vms_left(node, unplaced, need_online):
    """Log the VMs that evacuate leaves on the node, return True if there are any"""
    if unplaced:
        logging.error("Node %s not fully evacuated, no target for VM(s): %s", node.node, _vmids(unplaced))
    if need_online:
        logging.error("Node %s not fully evacuated, running VM(s) need --online: %s", node.node, _vmids(need_online))
    return bool(unplaced or need_online)
