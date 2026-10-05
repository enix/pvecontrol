import logging
import sys

import click

from pvecontrol.models.node import NodeStatus
from pvecontrol.models.vm import VmStatus
from pvecontrol.utils import print_task
from pvecontrol.cli import ResourceGroup, migration_related_command
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
@click.pass_context
# FIXME: remove pylint disable annotations
# pylint: disable=too-many-branches,too-many-statements,too-many-locals
def evacuate(ctx, node, target, dry_run, online, follow, wait, no_skip_stopped):
    """Evacuate a node by migrating all it's VM out to one or multiple target nodes"""
    # check node exists
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    srcnode = proxmox.find_node(node)
    logging.debug(srcnode)
    if not srcnode:
        logging.error("Node %s does not exist", node)
        sys.exit(1)
    # check node is online
    if srcnode.status != NodeStatus.ONLINE:
        logging.error("Node %s is not online", node)
        sys.exit(1)

    targets = []
    # compute targets migration possible
    if target:
        for pattern in list(set(target)):
            nodes = proxmox.find_nodes(pattern)
            if not nodes:
                logging.warning("No node match the pattern %s, skipping", pattern)
                continue
            # FIXME: remove pylint disable annotation
            # pylint: disable=redefined-argument-from-local
            for node in nodes:
                if node.node == srcnode.node:
                    logging.warning("Target node %s is the same as source node, skipping", node.node)
                    continue
                if node.status != NodeStatus.ONLINE:
                    logging.warning("Target node %s is not online, skipping", node.node)
                    continue
                targets.append(node)
    else:
        targets = [n for n in proxmox.nodes if n.status == NodeStatus.ONLINE and n.node != srcnode.node]
    if len(targets) == 0:
        logging.error("No target node available")
        sys.exit(1)
    # Make sure there is no duplicate in targets
    targets = list(set(targets))
    logging.debug("Migration targets: %s", ([t.node for t in targets]))

    plan = []
    unplaced = []
    need_online = []
    for vm in srcnode.vms:
        logging.debug("Selecting node for VM: %i, maxmem: %i, cpus: %i", vm.vmid, vm.maxmem, vm.cpus)
        if vm.status != VmStatus.RUNNING and not no_skip_stopped:
            logging.debug("VM %i is not running, skipping", vm.vmid)
            continue
        # PVE refuses to migrate a running VM offline
        if vm.status == VmStatus.RUNNING and not online:
            logging.warning("VM %s (%s) is running, use --online to migrate it, skipping", vm.vmid, vm.name)
            need_online.append(vm)
            continue
        # check ressources
        # FIXME: remove pylint disable annotation
        # pylint: disable=redefined-argument-from-local
        for target in targets:
            logging.debug(
                "Test target: %s, allocatedmem: %i, allocatedcpu: %i",
                target.node,
                target.allocatedmem,
                target.allocatedcpu,
            )
            if (vm.maxmem + target.allocatedmem) > (target.maxmem - proxmox.config["node"]["memoryminimum"]):
                logging.debug("Discard target: %s, will overcommit ram", target.node)
            elif (vm.cpus + target.allocatedcpu) > (target.maxcpu * proxmox.config["node"]["cpufactor"]):
                logging.debug("Discard target: %s, will overcommit cpu", target.node)
            else:
                plan.append(
                    {
                        "vmid": vm.vmid,
                        "vm": vm,
                        "node": srcnode,
                        "target": target,
                    }
                )
                target.allocatedmem += vm.maxmem
                target.allocatedcpu += vm.cpus
                logging.debug(
                    "Selected target %s: new allocatedmem %i, new allocatedcpu %i",
                    target.node,
                    target.allocatedmem,
                    target.allocatedcpu,
                )
                break
        else:
            logging.warning("No target found for VM %s (%s), skipping", vm.vmid, vm.name)
            unplaced.append(vm)

    logging.debug(plan)
    # validate input
    if len(plan) == 0:
        if _log_vms_left(srcnode, unplaced, need_online):
            sys.exit(1)
        logging.info("No VM to migrate")
        return
    for p in plan:
        print(f"Migrating VM {p['vmid']} ({p['vm'].name}) from {p['node'].node} to {p['target'].node}")
    confirmation = input("Confirm (yes):")
    logging.debug("Confirmation input: %s", confirmation)
    if confirmation.lower() != "yes":
        logging.error("Aborting")
        sys.exit(1)
    # run migrations

    failed = []
    for p in plan:
        print(f"Migrate VM: {p['vmid']} / {p['vm'].name} from {p['node'].node} to {p['target'].node}")
        if not dry_run:
            upid = p["vm"].migrate(p["target"].node, online)
            logging.debug("Migration UPID: %s", upid)
            proxmox.refresh()
            task = print_task(proxmox, upid, follow, wait)
            # Without --follow or --wait the task is usually still running and its result is unknown
            if not task.running() and not task.vanished() and task.exitstatus != "OK":
                failed.append(p["vm"])
        else:
            print("Dry run, skipping migration")

    if failed:
        logging.error("Migration failed for VM(s): %s", _vmids(failed))
    if _log_vms_left(srcnode, unplaced, need_online) or failed:
        sys.exit(1)


def _vmids(vms):
    return ", ".join(str(vm.vmid) for vm in vms)


def _log_vms_left(node, unplaced, need_online):
    """Log the VMs that evacuate leaves on the node, return True if there are any"""
    if unplaced:
        logging.error("Node %s not fully evacuated, no target for VM(s): %s", node.node, _vmids(unplaced))
    if need_online:
        logging.error("Node %s not fully evacuated, running VM(s) need --online: %s", node.node, _vmids(need_online))
    return bool(unplaced or need_online)
