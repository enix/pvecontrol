import sys
from itertools import chain
import click

from pvecontrol.models.cluster import PVECluster
from pvecontrol.models.node import PVENode
from pvecontrol.models.vm import PVEVm
from ortools.sat.python import cp_model

# import numpy as np


@click.command()
@click.option(
    "-a", "--anti-affinity", default="", help="Balance machine with those comma-separated prefixes across nodes"
)
@click.option("-p", "--movement-penalty", default=0, type=int, help="Higher values minimize VM movement")
@click.option("-d", "--dry-run", is_flag=True, help="Only print the `vm migrate` commands, doesn't take action")
@click.pass_context
def balance(ctx, anti_affinity, movement_penalty, dry_run):
    """Balances VMs across nodes in the cluster"""
    overcommit_factor = 1.2
    proxmox: PVECluster = PVECluster.create_from_config(ctx.obj["args"].cluster)
    nodes: list[PVENode] = proxmox.nodes
    # keep only non-template instances
    vms: list[PVEVm] = list(filter(lambda vm: vm.template == 0, chain.from_iterable(node.vms for node in nodes)))
    vms_count = len(vms)
    nodes_count = len(nodes)
    vm_params = [{"cpu": vm.cpus, "memory": vm.maxmem} for vm in vms]
    node_caps = list({"cpu": node.maxcpu, "memory": node.maxmem} for node in nodes)
    vm_groups = {
        aag: list(map(lambda i: i[0], filter(lambda x: aag in x[1].name, enumerate(vms))))
        for aag in anti_affinity.split(",")
    }

    node_map = {vm.name: node_idx for node_idx, node in enumerate(nodes) for vm in node.vms}
    initial_locations = {i: node_map.get(vm.name) for i, vm in enumerate(vms) if vm.name in node_map}

    model = cp_model.CpModel()
    vm_to_nodes = {
        (vm_index, node_index): model.NewBoolVar(f"vm_{vm_index}_to_node_{node_index}")
        for vm_index in range(vms_count)
        for node_index in range(nodes_count)
    }

    for vm_index in range(vms_count):
        model.Add(sum(vm_to_nodes[(vm_index, node_index)] for node_index in range(nodes_count)) == 1)

    for node_index in range(nodes_count):
        overcomitted_cpu_cap = int(node_caps[node_index]["cpu"] * overcommit_factor)
        resources = {"cpu": overcomitted_cpu_cap, "memory": node_caps[node_index]["memory"]}
        for k, v in resources.items():
            model.Add(
                sum(vm_params[vm_index][k] * vm_to_nodes[(vm_index, node_index)] for vm_index in range(vms_count)) <= v
            )

    obj_terms = []
    for gid, vm_indices in vm_groups.items():
        if not vm_indices:
            continue

        max_vms_in_node = model.NewIntVar(0, len(vm_indices), f"max_vms_from_group_{gid}")

        group_vms_per_node = {}
        for node_index in range(nodes_count):
            group_vms_per_node[node_index] = model.NewIntVar(
                0, len(vm_indices), f"group_{gid}_vms_in_node_{node_index}"
            )
            model.Add(
                group_vms_per_node[node_index] == sum(vm_to_nodes[(vm_index, node_index)] for vm_index in vm_indices)
            )
            model.Add(max_vms_in_node >= group_vms_per_node[node_index])

        obj_terms.append(max_vms_in_node * len(vm_indices) * 100)
        for node_index_start in range(nodes_count):
            for node_index_remain in range(node_index_start + 1, nodes_count):
                diff = model.NewIntVar(
                    0, len(vm_indices), f"diff_group_{gid}_nodes_{node_index_start}_{node_index_remain}"
                )
                model.AddAbsEquality(diff, group_vms_per_node[node_index_start] - group_vms_per_node[node_index_remain])
                obj_terms.append(diff * 10)

    vm_moved = {}
    for vm_index in range(vms_count):
        if node_index in initial_locations:
            vm_moved[vm_index] = model.NewBoolVar(f"vm_{vm_index}_moved")
            initial_node = initial_locations[vm_index]
            model.Add(vm_to_nodes[(vm_index, initial_node)] == 1).OnlyEnforceIf(vm_moved[vm_index].Not())
            model.Add(vm_to_nodes[(vm_index, initial_node)] == 0).OnlyEnforceIf(vm_moved[vm_index])
            obj_terms.append(vm_moved[vm_index] * movement_penalty)

    resource_per_node = {}
    max_resource = {}
    resources = {
        "cpu": {
            "max_cap": int(max(cap["cpu"] for cap in node_caps) * overcommit_factor),
            "node_cap": lambda node_index: int(node_caps[node_index]["cpu"] * overcommit_factor),
        },
        "memory": {
            "max_cap": max(cap["memory"] for cap in node_caps),
            "node_cap": lambda node_index: node_caps[node_index]["memory"],
        },
    }
    for rtype, rvalue in resources.items():
        resource_per_node[rtype] = {}
        for node_index in range(nodes_count):
            node_var = model.NewIntVar(0, rvalue["node_cap"](node_index), f"{rtype}_in_node_{node_index}")
            resource_per_node[rtype][node_index] = node_var
            model.Add(
                node_var
                == sum(
                    vm_params[vm_index][rtype] * vm_to_nodes[(vm_index, node_index)] for vm_index in range(vms_count)
                )
            )

        max_resource[rtype] = model.NewIntVar(0, rvalue["max_cap"], f"max_{rtype}")

    max_cpu = max_resource["cpu"]
    max_memory = max_resource["memory"]
    cpu_per_node = resource_per_node["cpu"]
    memory_per_node = resource_per_node["memory"]

    for node_index in range(nodes_count):
        model.Add(max_cpu >= cpu_per_node[node_index])
        model.Add(max_memory >= memory_per_node[node_index])

    obj_terms.append(max_cpu)
    obj_terms.append(max_memory)

    model.Minimize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    status = solver.Solve(model=model)
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        assignments = {}
        moves = []

        for vm_index in range(vms_count):
            for node_index in range(nodes_count):
                if solver.Value(vm_to_nodes[(vm_index, node_index)]) == 1:
                    assignments[vm_index] = node_index

                    if vm_index in initial_locations and initial_locations[vm_index] != node_index:
                        moves.append((vm_index, initial_locations[vm_index], node_index))
        # group_distributions = {}
        # group_variances = {}
        # for gid, vm_indices in vm_groups.items():
        #     if not vm_indices: continue

        #     group_dist = [0] * nodes_count
        #     for it in vm_indices:
        #         group_dist[assignments[it]] += 1

        #     group_distributions[gid] = group_dist
        #     group_variances[gid] = np.var(group_dist)

        for move in moves:
            print(f"{sys.argv[0]} vm migrate --target {nodes[move[2]].node} {vms[move[0]].vmid}")

    else:
        print("failed")
    # print(vm_params)
    # print(initial_locations)
    # # metrics = proxmox.metrics
    # print(anti_affinity)
    # print(movement_penalty)
    # print(dry_run)
