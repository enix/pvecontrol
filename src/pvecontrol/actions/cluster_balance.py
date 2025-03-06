
from itertools import product
from typing import List

import pulp

from pvecontrol.models.node import PVENode
from pvecontrol.models.vm import PVEVm


def rebalance(nodes: List[PVENode], vms: List[PVEVm], ram=False, cpu=False):
    node_names = [node.node for node in nodes]
    # pulp ops for each vm weight
    x = {}
    for vm, node in product(vms, node_names):
        x[vm.name, node] = pulp.LpVariable(f"x_{vm.name}_{node}", cat=pulp.LpBinary)
    model = pulp.LpProblem("Weight_Balancing", pulp.LpMinimize)

    if cpu:
        node_weights_cpu = {
            node: pulp.lpSum(vm.cpus * x[vm.name, node] for vm in vms) for node in node_names}
        maxw_cpu = pulp.LpVariable("maxw_cpu")
        minw_cpu = pulp.LpVariable("minw_cpu")
        model += maxw_cpu - minw_cpu
        for node in node_names:
            model += node_weights_cpu[node] <= maxw_cpu
            model += node_weights_cpu[node] >= minw_cpu

    if ram:
        node_weights_ram = {
            node: pulp.lpSum(vm.maxmem * x[vm.name, node] for vm in vms) for node in node_names}
        maxw_ram = pulp.LpVariable("maxw_ram")
        minw_ram = pulp.LpVariable("minw_ram")
        model += maxw_ram - minw_ram
        for node in node_names:
            model += node_weights_ram[node] <= maxw_ram
            model += node_weights_ram[node] >= minw_ram
    
    for vm in vms:
        model += pulp.lpSum(x[vm.name, node] for node in node_names) == 1

    # finally :)
    model.solve(pulp.PULP_CBC_CMD(msg=False))

    moves = []
    for vm in vms:
        orig = vm.node
        for node in node_names:
            if pulp.value(x[vm.name, node]) == 1 and node != orig:
                moves.append(dict(vmid = vm.vmid, node_to = node))

    return moves
