from dataclasses import dataclass, field

from pvecontrol.models import api_kwargs

RESOURCE_COLUMNS = [
    "vmid",
    "name",
    "node",
    "state",
    "ha_state",
    "max_restart",
    "max_relocate",
    "failback",
    "auto_rebalance",
    "rules",
    "comment",
]
RULE_COLUMNS = ["rule", "type", "affinity", "resources", "nodes", "strict", "state", "errors", "comment"]


def format_api_errors(errors):
    """Errors of the HA API, {option: [message, ...]} or {option: "message"}, as one line"""
    if not isinstance(errors, dict):
        return str(errors) if errors else ""
    return "; ".join(
        f"{option}: {', '.join(messages) if isinstance(messages, list) else messages}"
        for option, messages in errors.items()
    )


def sid_vmid(sid):
    """VMID of a "vm:100" resource id, None for another type of resource"""
    kind, _, name = sid.partition(":")
    return int(name) if kind == "vm" and name.isdigit() else None


@dataclass(eq=False)
class PVEHaResourceData:
    # cluster/ha/resources only returns the options that are set: the defaults are those of the API
    sid: str = field(default="")
    type: str = field(default="")
    state: str = field(default="started")
    max_restart: int = field(default=1)
    max_relocate: int = field(default=1)
    failback: bool = field(default=True)
    auto_rebalance: bool = field(default=True)
    comment: str = field(default="")


class PVEHaResource(PVEHaResourceData):
    """An HA resource, a VM managed by the HA manager.

    name and node come from the VM, ha_state from the HA manager status, rules from the HA rules: they are set by
    PVECluster.ha_resources.
    """

    def __init__(self, name="", node="", ha_state="-", rules=(), **kwargs):
        super().__init__(**kwargs)
        self.max_restart = int(self.max_restart)
        self.max_relocate = int(self.max_relocate)
        self.failback = bool(int(self.failback))
        self.auto_rebalance = bool(int(self.auto_rebalance))
        self.name = name
        self.node = node
        self.ha_state = ha_state
        self.rules = ",".join(rules)

    @classmethod
    def from_api(cls, payload, **kwargs):
        return cls(**kwargs, **api_kwargs(PVEHaResourceData, payload))

    @property
    def vmid(self):
        return sid_vmid(self.sid)


@dataclass(eq=False)
class PVEHaRuleData:
    rule: str = field(default="")
    type: str = field(default="")
    resources: str = field(default="")
    nodes: str = field(default="")
    affinity: str = field(default="")
    strict: bool = field(default=False)
    disable: bool = field(default=False)
    comment: str = field(default="")
    errors: str = field(default="")
    order: int = field(default=0)
    digest: str = field(default="")


class PVEHaRule(PVEHaRuleData):
    """An HA rule: node-affinity (resources and nodes) or resource-affinity (resources together or apart)"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.strict = bool(int(self.strict or 0))
        self.disable = bool(int(self.disable or 0))
        self.errors = format_api_errors(self.errors)
        if self.type == "node-affinity" and not self.affinity:
            self.affinity = "positive"
        # Only node affinity rules have the option, a resource affinity rule is always strict
        if self.type != "node-affinity":
            self.strict = "-"

    @classmethod
    def from_api(cls, payload):
        return cls(**api_kwargs(PVEHaRuleData, payload))

    @property
    def sids(self):
        return [sid for sid in self.resources.split(",") if sid]

    @property
    def state(self):
        return "disabled" if self.disable else "enabled"


def _node_names(nodes):
    return [item.split(":")[0] for item in nodes.split(",") if item]


def rule_conflicts(rule, others, cluster_nodes):
    """Why Proxmox VE would refuse the rule, for the feasibility checks that depend on this rule and its overlap with
    the other enabled rules. The API runs them too, but its error doesn't tell which one failed."""
    if rule.disable:
        return []
    sids = set(rule.sids)
    others = [other for other in others if not other.disable and other.rule != rule.rule]
    conflicts = []
    if rule.type == "node-affinity":
        if rule.affinity == "negative":
            if any(":" in item for item in rule.nodes.split(",")):
                conflicts.append("a negative node affinity rule can't give node priorities")
            if set(cluster_nodes) <= set(_node_names(rule.nodes)):
                conflicts.append("a negative node affinity rule can't list every node of the cluster")
        for other in others:
            shared = sids & set(other.sids)
            if other.type == "node-affinity" and shared:
                conflicts.append(f"{', '.join(sorted(shared))} already in node affinity rule {other.rule}")
    else:
        if len(sids) < 2:
            conflicts.append("a resource affinity rule needs at least two resources")
        if rule.affinity == "negative" and len(sids) > len(cluster_nodes):
            conflicts.append(
                f"a negative resource affinity rule can't have more resources than nodes ({len(cluster_nodes)})"
            )
        for other in others:
            shared = sids & set(other.sids)
            if other.type == "resource-affinity" and other.affinity != rule.affinity and len(shared) >= 2:
                conflicts.append(
                    f"{', '.join(sorted(shared))} are also in {other.affinity} resource affinity rule {other.rule}"
                )
    return conflicts
