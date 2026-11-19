from proxmoxer.core import ResourceException

from pvecontrol.models.vm import VmStatus
from pvecontrol.sanitycheck.checks import Check, CheckType, CheckMessage, CheckCode

# Share of the memory of running VMs, in percent, above which the load not managed by HA is reported:
# the auto-rebalancer only moves HA resources, it can't balance the rest
NON_HA_MEMORY_SHARE_MAX = 50

# Modes where the HA manager runs the auto-rebalancer, it ignores ha-auto-rebalance in basic mode
REBALANCING_MODES = ("static", "dynamic")


def _percent(value):
    return f"{value:g}%"


class HaCrs(Check):

    id = "crs"
    type = CheckType.HA
    name = "Check HA Cluster Resource Scheduler"

    def run(self):
        try:
            crs = self.proxmox.crs
        except ResourceException as error:
            msg = f"CRS settings can't be read: {error}"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))
            return

        # The HA status only feeds the checks on resources and imbalance: the settings are checked without it
        try:
            resources = self.proxmox.ha["resources"]
            imbalance = self.proxmox.ha_imbalance
        except ResourceException as error:
            msg = f"HA status can't be read, HA resources and imbalance not checked: {error}"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))
            resources = imbalance = None

        if crs.mode == "basic" and resources:
            msg = "CRS mode basic places HA resources by count, ignoring CPU and memory: use static or dynamic"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))

        if crs.auto_rebalance:
            self._check_auto_rebalance(crs, resources)

        # Rounded, so that a 0.3 fraction is not above a 30% threshold because of the float arithmetic
        imbalance_percent = None if imbalance is None else round(imbalance * 100, 6)
        if imbalance_percent is not None and imbalance_percent > crs.threshold:
            state = "enabled" if crs.auto_rebalance else "disabled"
            msg = (
                f"HA imbalance {imbalance_percent:.1f}% is above the threshold {_percent(crs.threshold)}, "
                f"auto-rebalance is {state}"
            )
            self.add_messages(CheckMessage(CheckCode.CRIT, msg))

        if not self.messages:
            msg = "CRS settings checked"
            self.add_messages(CheckMessage(CheckCode.OK, msg))

    def _check_auto_rebalance(self, crs, resources):
        if crs.mode not in REBALANCING_MODES:
            msg = f"Auto-rebalance is enabled but ignored in CRS mode {crs.mode}, use static or dynamic"
            self.add_messages(CheckMessage(CheckCode.CRIT, msg))
            return

        if crs.threshold == 0 and crs.margin == 0:
            msg = "Auto-rebalance is enabled but never runs, threshold and margin are both 0"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))
            return

        if crs.margin == 0:
            msg = "Auto-rebalance margin is 0, migrations may not improve the balance (ping-pong)"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))
        if crs.hold_duration == 0:
            msg = "Auto-rebalance hold duration is 0, it reacts on the first imbalanced round"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))

        if resources is None:
            return

        if not self._movable_resources(resources):
            if resources:
                msg = (
                    "Auto-rebalance is enabled but no HA resource can be moved, "
                    "all have auto-rebalance disabled or a positive affinity with one that has"
                )
            else:
                msg = "Auto-rebalance is enabled but there is no HA resource to move"
            self.add_messages(CheckMessage(CheckCode.WARN, msg))

        self._check_non_ha_load(resources)

    def _movable_resources(self, resources):
        """The HA resources the auto-rebalancer may move.

        A resource with auto-rebalance=0 is excluded, and so is every resource tied to an excluded one by a
        positive resource-affinity rule, as they must stay together.
        """
        sids = {resource["sid"] for resource in resources}
        excluded = {resource["sid"] for resource in resources if not int(resource.get("auto-rebalance", 1))}
        # Legacy HA groups have no type and are skipped
        groups = [
            set(rule.get("resources", "").split(","))
            for rule in self.proxmox.ha["groups"]
            if rule.get("type") == "resource-affinity"
            and rule.get("affinity") == "positive"
            and not int(rule.get("disable", 0))
        ]
        # Positive affinities chain: repeat until no group adds an exclusion
        changed = True
        while changed:
            changed = False
            for group in groups:
                if group & excluded and not group <= excluded:
                    excluded |= group
                    changed = True
        return sids - excluded

    def _check_non_ha_load(self, resources):
        ha_sids = {resource["sid"] for resource in resources}
        running = [vm for vm in self.proxmox.vms if vm.status == VmStatus.RUNNING]
        total = sum(vm.maxmem for vm in running)
        if not total:
            return
        non_ha = sum(vm.maxmem for vm in running if f"vm:{vm.vmid}" not in ha_sids)
        share = non_ha * 100 / total
        if share > NON_HA_MEMORY_SHARE_MAX:
            msg = f"{share:.0f}% of the memory of running VMs is not managed by HA, auto-rebalance can't move it"
            self.add_messages(CheckMessage(CheckCode.INFO, msg))
