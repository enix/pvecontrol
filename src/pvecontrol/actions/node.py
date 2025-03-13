import logging

import click

from pvecontrol.models.node import NodeStatus
from pvecontrol.models.vm import VmStatus
from pvecontrol.utils import print_output, print_task, with_table_options, migration_related_command
from pvecontrol.models.node import COLUMNS
from pvecontrol.models.cluster import PVECluster


@click.group()
def root():
    """Node related commands"""


@root.command("list")
@with_table_options(COLUMNS, "node")
@click.pass_context
def node_list(ctx, sort_by, columns, filters):
    """List nodes in the cluster"""
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    output = ctx.obj["args"].output
    print_output(proxmox.nodes, columns=columns, sortby=sort_by, filters=filters, output=output)


@root.command()
@click.argument("node", required=True)
@click.argument("target", nargs=-1)
@migration_related_command
@click.option("--no-skip-stopped", is_flag=True, help="Don't skip VMs that are stopped")
@click.pass_context
# FIXME: remove pylint disable annotations
# pylint: disable=too-many-branches,too-many-statements,too-many-locals
def evacuate(ctx, node, target, follow, wait, dry_run, online, no_skip_stopped):
    """Evacuate a node by migrating all it's VM out to one or multiple target nodes"""
    # check node exists
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    srcnode = proxmox.find_node(node)
    logging.debug(srcnode)
    if not srcnode:
        print(f"Node {node} does not exist")
        return
    # check node is online
    if srcnode.status != NodeStatus.ONLINE:
        print(f"Node {node} is not online")
        return

    targets = []
    # compute targets migration possible
    if target:
        for pattern in list(set(target)):
            nodes = proxmox.find_nodes(pattern)
            if not nodes:
                print(f"No node match the pattern {pattern}, skipping")
                continue
            # FIXME: remove pylint disable annotation
            # pylint: disable=redefined-argument-from-local
            for node in nodes:
                if node.node == srcnode.node:
                    print(f"Target node {node.node} is the same as source node, skipping")
                    continue
                if node.status != NodeStatus.ONLINE:
                    print(f"Target node {node.node} is not online, skipping")
                    continue
                targets.append(node)
    else:
        targets = [n for n in proxmox.nodes if n.status == NodeStatus.ONLINE and n.node != srcnode.node]
    if len(targets) == 0:
        print("No target node available")
        return
    # Make sure there is no duplicate in targets
    targets = list(set(targets))
    logging.debug("Migration targets: %s", ([t.node for t in targets]))

    plan = []
    for vm in srcnode.vms:
        logging.debug("Selecting node for VM: %i, maxmem: %i, cpus: %i", vm.vmid, vm.maxmem, vm.cpus)
        if vm.status != VmStatus.RUNNING and not no_skip_stopped:
            logging.debug("VM %i is not running, skipping", vm.vmid)
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
                        "node": node,
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
            print("No target found for VM %s", vm.vmid)

    logging.debug(plan)
    # validate input
    if len(plan) == 0:
        print("No VM to migrate")
        return
    for p in plan:
        print(f"Migrating VM {p['vmid']} ({p['vm'].name}) from {p['node']} to {p['target'].node}")
    confirmation = input("Confirm (yes):")
    logging.debug("Confirmation input: %s", confirmation)
    if confirmation.lower() != "yes":
        print("Aborting")
        return
    # run migrations

    for p in plan:
        print(f"Migrate VM: {p['vmid']} / {p['vm'].name} from {p['node']} to {p['target'].node}")
        if not dry_run:
            upid = p["vm"].migrate(p["target"].node, online)
            logging.debug("Migration UPID: %s", upid)
            proxmox.refresh()
            _task = proxmox.find_task(upid)
            print_task(proxmox, upid, follow, wait)
        else:
            print("Dry run, skipping migration")
