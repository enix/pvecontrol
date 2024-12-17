import logging

from pvecontrol.node import NodeStatus
from pvecontrol.vm import VmStatus
from pvecontrol.utils import print_tableoutput, print_task


def action_nodelist(proxmox, args):
    """List proxmox nodes in the cluster using proxmoxer api"""
    print_tableoutput(proxmox.nodes, columns=args.columns, sortby=args.sort_by, filters=args.filter)


# pylint: disable=too-many-branches,too-many-statements
def action_nodeevacuate(proxmox, args):
    """Evacuate a node by migrating all it's VM out"""
    # check node exists
    srcnode = proxmox.find_node(args.node)
    logging.debug(srcnode)
    if not srcnode:
        print(f"Node {args.node} does not exist")
        return
    # check node is online
    if srcnode.status != NodeStatus.ONLINE:
        print(f"Node {args.node} is not online")
        return

    targets = []
    # compute targets migration possible
    if args.target:
        for pattern in list(set(args.target)):
            nodes = proxmox.find_nodes(pattern)
            if not nodes:
                print(f"No node match the pattern {pattern}, skipping")
                continue
            for node in nodes:
                if node.node == srcnode.node:
                    print(f"Target node {pattern} is the same as source node, skipping")
                    continue
                if node.status != NodeStatus.ONLINE:
                    print(f"Target node {pattern} is not online, skipping")
                    continue
                targets.append(node)
    else:
        targets = [n for n in proxmox.nodes if n.status == NodeStatus.ONLINE and n.node != srcnode.node]
    if len(targets) == 0:
        print("No target node available")
        return
    logging.debug("Migration targets: %s", ([t.node for t in targets]))

    plan = []
    for vm in srcnode.vms:
        logging.debug("Selecting node for VM: %i, maxmem: %i, cpus: %i", vm.vmid, vm.maxmem, vm.cpus)
        if vm.status != VmStatus.RUNNING and not args.no_skip_stopped:
            logging.debug("VM %i is not running, skipping", vm.vmid)
            continue
        # check ressources
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
                        "node": args.node,
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
        if not args.dry_run:
            upid = p["vm"].migrate(p["target"].node, args.online)
            logging.debug("Migration UPID: %s", upid)
            proxmox.refresh()
            _task = proxmox.find_task(upid)
            print_task(proxmox, upid, args.follow, args.wait)
        else:
            print("Dry run, skipping migration")
