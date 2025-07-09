import sys
from itertools import chain
import click
from ortools.sat.python import cp_model

# displayer requires
import rich
from rich.tree import Tree
from rich.panel import Panel
from rich.columns import Columns

from pvecontrol.models.cluster import PVECluster
from pvecontrol.models.vm import PVEVm, VmStatus


def displayer(vms: list[PVEVm], px: PVECluster, moves):
    def draw_tree(color):
        t = Tree(px.name)
        for node in sorted(px.nodes, key=lambda n: n.node):
            n = t.add(f"[cyan][b]{node.node}[/b]")
            node_vms = [vm for vm in vms if vm.node == node.node]
            for vm in node_vms:
                if vms.index(vm) in [m[0] for m in moves]:
                    n.add(f"[{color}]{ vm.name }")
                else:
                    n.add(f"{vm.name}")
        return t

    before = draw_tree("red")
    for move in moves:
        vms[move[0]].node = px.nodes[move[2]].node
    after = draw_tree("green")
    rich.print(Columns([Panel(before), Panel(after)]))


def __vm_to_nodes(model, nodes, vms, node_caps, vm_params, overcommit):
    # list all possible placement in this cluster (vm * node)
    vm_to_nodes: dict[tuple[int, int], cp_model.IntVar] = {
        (vm_index, node_index): model.NewBoolVar(f"vm_{vm_index}_to_node_{node_index}")
        for vm_index, _ in enumerate(vms)
        for node_index, _ in enumerate(nodes)
    }

    # a given vm should exist in *only one* node
    for vm_index, _ in enumerate(vms):
        model.Add(sum(vm_to_nodes[(vm_index, node_index)] for node_index, _ in enumerate(nodes)) == 1)

    # a node can allocate only its overcommit*cpus, and only its ram
    for node_index, _ in enumerate(nodes):
        overcomitted_cpu_cap = int(node_caps[node_index]["cpu"] * overcommit)
        resources = {"cpu": overcomitted_cpu_cap, "memory": node_caps[node_index]["memory"]}
        for k, v in resources.items():
            model.Add(sum(vm_params[i][k] * vm_to_nodes[(i, node_index)] for i, _ in enumerate(vms)) <= v)
    return vm_to_nodes


def __constraints_antiaffinities_nodes(model, nodes, vm_to_nodes, vm_antiaffinity_groups):
    obj_terms: list[cp_model.IntVar] = []
    # there should be as few antiaffinity groups members per node as possible (this implies they'll be spread as
    # much as possible)
    for gid, vm_indices in vm_antiaffinity_groups.items():
        if not vm_indices:
            continue

        max_vms_in_node = model.NewIntVar(0, len(vm_indices), f"max_vms_from_group_{gid}")

        group_vms_per_node = {}
        for node_index, _ in enumerate(nodes):
            group_vms_per_node[node_index] = model.NewIntVar(
                0, len(vm_indices), f"group_{gid}_vms_in_node_{node_index}"
            )
            model.Add(
                group_vms_per_node[node_index] == sum(vm_to_nodes[(vm_index, node_index)] for vm_index in vm_indices)
            )
            model.Add(max_vms_in_node >= group_vms_per_node[node_index])

        obj_terms.append(max_vms_in_node * len(vm_indices) * 100)
        for node_index_start, _ in enumerate(nodes):
            for node_index_remain in range(node_index_start + 1, len(nodes)):
                diff = model.NewIntVar(
                    0, len(vm_indices), f"diff_group_{gid}_nodes_{node_index_start}_{node_index_remain}"
                )
                model.AddAbsEquality(diff, group_vms_per_node[node_index_start] - group_vms_per_node[node_index_remain])
                obj_terms.append(diff * 10)
    return obj_terms


def __constraints_resources_vm(
    model, nodes, vms, initial_locations, vm_to_nodes, overcommit, node_caps, vm_params, movement_penalty
):
    obj_terms = []
    resources = {
        "cpu": {
            "max_cap": int(max(cap["cpu"] for cap in node_caps) * overcommit),
            "node_cap": lambda node_index: int(node_caps[node_index]["cpu"] * overcommit),
        },
        "memory": {
            "max_cap": max(cap["memory"] for cap in node_caps),
            "node_cap": lambda node_index: node_caps[node_index]["memory"],
        },
    }

    def __gather_movements():
        vm_moved = {}
        # we add the movement penalty to our contraints, the solution will carry "non-moving" VM account for these
        for node_index, _ in enumerate(nodes):
            for vm_index, _ in enumerate(vms):
                if node_index in initial_locations:
                    vm_moved[vm_index] = model.NewBoolVar(f"vm_{vm_index}_moved")
                    initial_node = initial_locations[vm_index]
                    model.Add(vm_to_nodes[(vm_index, initial_node)] == 1).OnlyEnforceIf(vm_moved[vm_index].Not())
                    model.Add(vm_to_nodes[(vm_index, initial_node)] == 0).OnlyEnforceIf(vm_moved[vm_index])
                    obj_terms.append(vm_moved[vm_index] * movement_penalty)

    # even when overcommitting, we deal with discrete cpu core counts
    def __constraint_resources():
        resource_per_node = {}
        max_resource = {}
        for rtype, rvalue in resources.items():
            resource_per_node[rtype] = {}
            for node_index, _ in enumerate(nodes):
                node_var = model.NewIntVar(0, rvalue["node_cap"](node_index), f"{rtype}_in_node_{node_index}")
                resource_per_node[rtype][node_index] = node_var
                model.Add(
                    node_var == sum(vm_params[i][rtype] * vm_to_nodes[(i, node_index)] for i, _ in enumerate(vms))
                )

            max_resource[rtype] = model.NewIntVar(0, rvalue["max_cap"], f"max_{rtype}")

        for node_index, _ in enumerate(nodes):
            model.Add(max_resource["cpu"] >= resource_per_node["cpu"][node_index])
            model.Add(max_resource["memory"] >= resource_per_node["memory"][node_index])

        obj_terms.append(max_resource["cpu"])
        obj_terms.append(max_resource["memory"])

    __gather_movements()
    __constraint_resources()

    return obj_terms


def __solve_model(solver, model, vms, nodes, initial_locations, vm_to_nodes, rich_display, proxmox):
    if solver.Solve(model=model) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments = {}
        moves = []

        for vm_index, _ in enumerate(vms):
            for node_index, _ in enumerate(nodes):
                if solver.Value(vm_to_nodes[(vm_index, node_index)]) == 1:
                    assignments[vm_index] = node_index

                    if vm_index in initial_locations and initial_locations[vm_index] != node_index:
                        moves.append((vm_index, initial_locations[vm_index], node_index))

        if rich_display:
            displayer(vms, proxmox, moves)

        for move in moves:
            print(f"{sys.argv[0]} vm migrate --target {nodes[move[2]].node} {vms[move[0]].vmid}")

    else:
        print(
            "# an optimal couldn't be found, give it more time (using -t), set a bigger overcommit, provision more nodes"
        )


# we build anti-affinity as such : {'group_name': [list of vm indices with matching name]}
def __gather_antiaffinity_groups(vms, anti_affinity, anti_affinity_tags):
    vm_antiaffinity_groups = {}
    for aag in anti_affinity.split(","):
        vm_antiaffinity_groups[aag] = [i for i, vm in enumerate(vms) if aag in vm.name]
    for aat in anti_affinity_tags.split(","):
        vm_antiaffinity_groups[aat] = [i for i, vm in enumerate(vms) if aat in vm.tags]
    return vm_antiaffinity_groups


def __nodes_map(nodes):
    return {vm.vmid: node_idx for node_idx, node in enumerate(nodes) for vm in node.vms}


@click.command()
@click.option("-a", "--anti-affinity", default="", help="Balance machines with comma-separated patterns across nodes")
@click.option("-t", "--anti-affinity-tags", default="", help="Balance machines with comma-separated tags across nodes")
@click.option("-p", "--movement-penalty", default=0, type=int, help="Higher values minimize VM movements")
# FIXME: this is the only behavior for now
# @click.option("-d", "--dry-run", is_flag=True, help="Only print the `vm migrate` commands, doesn't take action")
@click.option("-r", "--running", is_flag=True, help="Balance only the currently running instances")
@click.option("-R", "--rich-display", is_flag=True, help="Use rich display")
@click.option(
    "--timeout",
    type=float,
    default=60.0,
    help="Limit calculation time, tiny values will result in sub-optimal solution",
)
@click.option("--overcommit", type=float, default=1.0, help="Sets an overcommit ratio regarding CPU nodes requirements")
@click.pass_context
# def balance(ctx, anti_affinity, anti_affinity_tags, movement_penalty, dry_run, running, rich_display):
def balance(ctx, anti_affinity, anti_affinity_tags, movement_penalty, running, rich_display, timeout, overcommit):
    """Balances VMs across nodes in the cluster, bear in mind the model used won't give the same result upon every calls"""
    proxmox: PVECluster = PVECluster.create_from_config(ctx.obj["args"].cluster)
    # keep only non-template instances
    vms: list[PVEVm] = list(
        filter(lambda vm: vm.template == 0, chain.from_iterable(node.vms for node in proxmox.nodes))
    )
    if running:
        vms = list(filter(lambda vm: vm.status == VmStatus.RUNNING, vms))

    vm_antiaffinity_groups = __gather_antiaffinity_groups(vms, anti_affinity, anti_affinity_tags)
    nodes_map = __nodes_map(proxmox.nodes)
    model = cp_model.CpModel()
    vm_to_nodes = __vm_to_nodes(
        model,
        proxmox.nodes,
        vms,
        [{"cpu": node.maxcpu, "memory": node.maxmem} for node in proxmox.nodes],
        [{"cpu": vm.cpus, "memory": vm.maxmem} for vm in vms],
        overcommit,
    )
    model.Minimize(
        sum(
            __constraints_antiaffinities_nodes(model, proxmox.nodes, vm_to_nodes, vm_antiaffinity_groups)
            + __constraints_resources_vm(
                model,
                proxmox.nodes,
                vms,
                {i: nodes_map.get(vm.vmid) for i, vm in enumerate(vms) if vm.vmid in nodes_map},
                vm_to_nodes,
                overcommit,
                [{"cpu": node.maxcpu, "memory": node.maxmem} for node in proxmox.nodes],
                [{"cpu": vm.cpus, "memory": vm.maxmem} for vm in vms],
                movement_penalty,
            )
        )
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout
    __solve_model(
        solver,
        model,
        vms,
        proxmox.nodes,
        {i: nodes_map.get(vm.vmid) for i, vm in enumerate(vms) if vm.vmid in nodes_map},
        vm_to_nodes,
        rich_display,
        proxmox,
    )
