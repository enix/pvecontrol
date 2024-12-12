from pvecontrol.sanitycheck.checks import Check, CheckCode, CheckType, CheckMessage


class Nodes(Check):

    id = "nodes"
    type = CheckType.NODE
    name = "Check Node capacity"

    def run(self):
        self._check_cpu_overcommit()
        self._check_mem_overcommit()

    def _check_mem_overcommit(self):
        for node in self.proxmox.nodes:
            if self._mem_is_overcommited(node.maxmem, self.proxmox.config["node"]["memoryminimum"], node.allocatedmem):
                msg = f"Node '{node.node}' is in mem overcommit status: {node.allocatedmem} allocated but {node.maxmem} available"
                self.add_messages(CheckMessage(CheckCode.CRIT, msg))
            else:
                msg = f"Node '{node.node}' isn't in mem overcommit"
                self.add_messages(CheckMessage(CheckCode.OK, msg))

    def _check_cpu_overcommit(self):
        for node in self.proxmox.nodes:
            if self._cpu_is_overcommited(node.maxcpu, self.proxmox.config["node"]["cpufactor"], node.allocatedcpu):
                msg = f"Node {node.node} is in cpu overcommit status: {node.allocatedcpu} allocated but {node.maxcpu} available"
                self.add_messages(CheckMessage(CheckCode.WARN, msg))
            else:
                msg = f"Node '{node.node}' isn't in cpu overcommit"
                self.add_messages(CheckMessage(CheckCode.OK, msg))

    def _cpu_is_overcommited(self, maxcpu, cpufactor, allocated_cpu):
        return (maxcpu * cpufactor) <= allocated_cpu

    def _mem_is_overcommited(self, max_mem, min_mem, allocated_mem):
        return (allocated_mem + min_mem) >= max_mem
