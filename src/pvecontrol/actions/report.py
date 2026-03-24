import contextlib
import io
from datetime import datetime

import click

from humanize import naturalsize

from pvecontrol.models.cluster import PVECluster
from pvecontrol.models.storage import PVEStorage
from pvecontrol.sanitycheck.sanitychecks import SanityCheck
from pvecontrol.sanitycheck.tests import DEFAULT_CHECK_IDS
from pvecontrol.utils import OutputFormats, render_output


def _build_resource_overview(metrics):
    cpu_total = metrics["cpu"]["total"]
    mem_total = metrics["memory"]["total"]
    return [
        {
            "resource": "CPU",
            "total": cpu_total,
            "used": f"{metrics['cpu']['usage']:.2f}",
            "percent used": f"{metrics['cpu']['percent']:.1f}%",
            "allocated": metrics["cpu"]["allocated"],
            "percent allocated": f"{metrics['cpu']['allocated'] / cpu_total * 100:.1f}%" if cpu_total else "N/A",
        },
        {
            "resource": "Memory",
            "total": naturalsize(mem_total, binary=True),
            "used": naturalsize(metrics["memory"]["usage"], binary=True),
            "percent used": f"{metrics['memory']['percent']:.1f}%",
            "allocated": naturalsize(metrics["memory"]["allocated"], binary=True),
            "percent allocated": (f"{metrics['memory']['allocated'] / mem_total * 100:.1f}%" if mem_total else "N/A"),
        },
        {
            "resource": "Disk",
            "total": naturalsize(metrics["disk"]["total"], binary=True),
            "used": naturalsize(metrics["disk"]["usage"], binary=True),
            "percent used": f"{metrics['disk']['percent']:.1f}%",
            "allocated": "-",
            "percent allocated": "-",
        },
    ]


def _build_ha_vmid_group_mapping(proxmox):
    """Build a vmid -> group name mapping, handling both old and new Proxmox HA APIs."""
    mapping = {}
    # New API (>= 9.1): each group/rule has a 'resources' field listing its VMs
    for group in proxmox.ha["groups"]:
        group_name = group.get("group") or group.get("rule", "")
        for sid in group.get("resources", "").split(","):
            if sid.startswith("vm:"):
                mapping[int(sid.split(":")[1])] = group_name
    # Old API (< 9.1): each HA resource has a 'group' field
    if not mapping:
        for resource in proxmox.ha["resources"]:
            if resource["type"] == "vm" and resource.get("group"):
                mapping[int(resource["sid"].split(":")[1])] = resource["group"]
    return mapping


def _build_ha_groups_data(proxmox):
    ha_groups = proxmox.ha["groups"]
    vmid_group_mapping = _build_ha_vmid_group_mapping(proxmox)
    vms_by_group = {}
    for vmid, group_name in vmid_group_mapping.items():
        vms_by_group.setdefault(group_name, []).append(vmid)

    return [
        {
            "group": group.get("group") or group.get("rule", ""),
            "nodes": group.get("nodes", ""),
            "node count": len(group["nodes"].split(",")) if group.get("nodes") else 0,
            "vms": len(vms_by_group.get(group.get("group") or group.get("rule", ""), [])),
        }
        for group in ha_groups
    ]


def _backup_job_vm_selection(job):
    if job.pool is not None:
        return f"Pool: {job.pool}"
    if job.all:
        excluded = [v for v in job.exclude if v]
        if excluded:
            return f"All VMs (exclude: {', '.join(excluded)})"
        return "All VMs"
    vmids = [v for v in job.vmid if v]
    return ", ".join(vmids) if vmids else ""


def _build_users_data(proxmox):
    users = []
    for user in proxmox.users:
        expire_str = datetime.fromtimestamp(user.expire).strftime("%Y-%m-%d") if user.expire else "Never"
        users.append(
            {
                "userid": user.userid,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "email": user.email,
                "realm-type": user.realm_type,
                "enabled": "Yes" if user.enable else "No",
                "expire": expire_str,
                "groups": ", ".join(user.groups),
            }
        )
    return users


def _build_sanity_check_section(proxmox):
    sc = SanityCheck(proxmox, colors=False, unicode=False)
    sc.run(checks=DEFAULT_CHECK_IDS)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sc.display()
    return buf.getvalue()


def _build_backup_jobs_data(proxmox):
    return [
        {
            "id": job.id,
            "target storage": job.storage,
            "schedule": job.schedule,
            "nodes": job.node or "All",
            "enabled": "Yes" if job.enabled else "No",
            "vm selection": _backup_job_vm_selection(job),
        }
        for job in proxmox.backup_jobs
    ]


def _build_vm_summary(all_vms, templates):
    vm_running = sum(1 for vm in all_vms if vm.status.name == "RUNNING")
    return [
        {
            "total": len(all_vms),
            "running": vm_running,
            "stopped": len(all_vms) - vm_running,
            "templates": len(templates),
        }
    ]


def _build_report_data(proxmox):
    metrics = proxmox.metrics
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    templates = [vm for vm in proxmox.vms if vm.template]
    all_vms = [vm for vm in proxmox.vms if not vm.template]

    # Nodes
    nodes_data = [
        {
            "node": node.node,
            "status": node.status.name,
            "version": node.version["version"],
            "vms": len([vm for vm in node.vms if not vm.template]),
            "total cpu": node.maxcpu,
            "allocated cpu": node.allocatedcpu,
            "used cpu": f"{node.cpu:.2f}",
            "total memory": naturalsize(node.maxmem, binary=True),
            "allocated memory": naturalsize(node.allocatedmem, binary=True),
            "used memory": naturalsize(node.mem, binary=True),
        }
        for node in proxmox.nodes
    ]

    ha_group_by_vmid = _build_ha_vmid_group_mapping(proxmox)

    vm_list = [
        {
            "vmid": vm.vmid,
            "name": vm.name,
            "status": vm.status.name,
            "node": vm.node,
            "cpus": vm.cpus,
            "memory": vm.maxmem,
            "disk": vm.maxdisk,
            "template": "Yes" if vm.template else "No",
            "ha group": ha_group_by_vmid.get(vm.vmid, ""),
            "tags": ", ".join(sorted(vm.tags)) if vm.tags else "",
            "backup jobs": ", ".join(job.id for job in vm.get_backup_jobs(proxmox)),
        }
        for vm in sorted(proxmox.vms, key=lambda v: v.vmid)
    ]

    # Sanity checks must run before storages because get_flattened_grouped_list mutates PVEStorage objects
    sanity_checks = _build_sanity_check_section(proxmox)

    # Storage — extract only the columns we need to avoid serialization issues
    storage_columns = ["storage", "nodes", "shared", "usage", "maxdisk", "disk", "plugintype", "status"]
    node_count = len(proxmox.nodes)
    storages_data = [
        {col: item.get(col) for col in storage_columns} for item in PVEStorage.get_flattened_grouped_list(proxmox)
    ]
    for storage in storages_data:
        if storage.get("nodes") and len(storage["nodes"].split(", ")) == node_count:
            storage["nodes"] = "All"

    return {
        "generated_at": now,
        "cluster": proxmox.name,
        "cluster name": proxmox.cluster_name,
        "version": proxmox.version.get("version", "unknown"),
        "status": "healthy" if proxmox.is_healthy else "not healthy",
        "resource_overview": _build_resource_overview(metrics),
        "vm_summary": _build_vm_summary(all_vms, templates),
        "nodes": nodes_data,
        "ha_groups": _build_ha_groups_data(proxmox),
        "vm_list": vm_list,
        "storages": storages_data,
        "backup_jobs": _build_backup_jobs_data(proxmox),
        "users": _build_users_data(proxmox),
        "sanity_checks": sanity_checks,
    }


def _render_header(data):
    return [
        f"# Cluster Report: {data['cluster']}",
        "",
        f"- **Generated**: {data['generated_at']}",
        f"- **Cluster Name**: {data['cluster name']}",
        f"- **Version**: {data['version']}",
        f"- **Status**: {data['status']}",
        "",
    ]


def _render_report(data, output=OutputFormats.MARKDOWN):
    lines = _render_header(data)

    lines.append("## Resources Overview")
    lines.append("")
    lines.append("### Compute Resources")
    lines.append("")
    lines.append(render_output(data["resource_overview"], output=output))
    lines.append("")
    lines.append("### Virtual Machines")
    lines.append("")
    lines.append(render_output(data["vm_summary"], output=output))
    lines.append("")
    lines.append("### Users")
    lines.append("")
    if data["users"]:
        lines.append(render_output(data["users"], sortby="userid", output=output))
    lines.append("")

    lines.append("## Proxmox VE Nodes")
    lines.append("")
    lines.append(render_output(data["nodes"], sortby="node", output=output))
    lines.append("")

    lines.append("## High Availability Groups")
    lines.append("")
    if data["ha_groups"]:
        lines.append(render_output(data["ha_groups"], sortby="group", output=output))
    else:
        lines.append("No HA groups configured.")
    lines.append("")

    lines.append("## Storage")
    lines.append("")
    if data["storages"]:
        lines.append(render_output(data["storages"], output=output))
    else:
        lines.append("No storage data available.")
    lines.append("")

    lines.append("## Backup Jobs")
    lines.append("")
    if data["backup_jobs"]:
        lines.append(render_output(data["backup_jobs"], output=output))
    else:
        lines.append("No backup jobs configured.")
    lines.append("")

    lines.append("## Virtual Machines")
    lines.append("")
    if data["vm_list"]:
        lines.append(render_output(data["vm_list"], output=output))
    lines.append("")

    lines.append("## Sanity Checks")
    lines.append("")
    lines.append("```")
    lines.append(data["sanity_checks"])
    lines.append("```")

    return "\n".join(lines)


@click.command()
@click.pass_context
def report(ctx):
    """Generate a resource usage report for the cluster"""
    proxmox = PVECluster.create_from_config(ctx.obj["args"].cluster)
    output = ctx.obj["args"].output

    supported = [OutputFormats.TEXT, OutputFormats.MARKDOWN]
    if output not in supported:
        supported_str = ", ".join(str(f) for f in supported)
        raise click.UsageError(
            f"Output format '{output}' is not supported by this command. Supported formats: {supported_str}"
        )

    data = _build_report_data(proxmox)
    print(_render_report(data, output=output))
