import json
import requests


DEFAULT_VM_CONFIG = {
    "memory": "1024",
    "vmgenid": "00000000-0000-0000-0000-000000000000",
    "template": 1,
    "scsihw": "virtio-scsi-single",
    "serial0": "socket",
    "balloon": 0,
    "onboot": 1,
    "ide2": "local:9012/vm-9012-cloudinit.qcow2,media=cdrom",
    "agent": "1",
    "cores": 1,
    "numa": 1,
    "digest": "0000000000000000000000000000000000000000",
    "smbios1": "uuid=00000000-0000-0000-0000-000000000000",
    "boot": "order=scsi0;net0",
    "ostype": "l26",
    "sockets": 1,
    "machine": "q35",
    "net0": "virtio=00:00:00:00:00:00,bridge=vmbr0",
    "cpu": "x86-64-v2-AES",
    "rng0": "source=/dev/urandom",
    "scsi0": "local:9012/base-9012-disk-0.qcow2,size=2G,ssd=1",
    "name": "template.debian-12-bookworm-amd64",
}


def mock_api_requests(nodes, vms, backup_jobs=None, storage_resources=None, storage_content=None):
    routes = generate_routes(nodes, vms, backup_jobs, storage_resources, storage_content)

    def side_effect(method, url, **kwargs):
        print(f"{method} {url}")
        print(f"params: {kwargs['params']}")
        path = url.replace("https://host:8006", "")
        assert path in routes

        route = routes[path]
        data = route(method, **kwargs) if callable(route) else route

        content = json.dumps({"data": data})
        print(content + "\n")

        res = requests.Response()
        res.status_code = 200
        res._content = content.encode("utf-8")  # pylint: disable=protected-access
        return res

    return side_effect


def generate_routes(nodes, vms, backup_jobs, storage_resources=None, storage_contents=None):
    storage_resources = storage_resources or []

    routes = {
        "/api2/json/cluster/status": [
            {"type": "cluster", "version": 2, "quorate": 1, "nodes": len(nodes), "id": "cluster", "name": "devel"},
            *[n["status"] for n in nodes],
        ],
        "/api2/json/cluster/resources": [
            *[n["resource"] for n in nodes],
            *storage_resources,
            *vms,
        ],
        "/api2/json/nodes": [
            *[n["resource"] for n in nodes],
        ],
        "/api2/json/cluster/tasks": [],
        "/api2/json/cluster/ha/groups": [],
        "/api2/json/cluster/ha/status/manager_status": [],
        "/api2/json/cluster/ha/resources": [],
        "/api2/json/cluster/backup": backup_jobs,
        **generate_vm_routes(nodes, vms),
        **generate_storages_contents_routes(nodes, storage_resources, storage_contents),
    }

    print("ROUTES:")
    for route_path in routes.keys():
        print(route_path)
    print("")

    return routes


def generate_vm_routes(nodes, vms):
    routes = {}

    for node in nodes:
        name = node["status"]["name"]
        routes[f"/api2/json/nodes/{name}/qemu"] = []

    for vm in vms:
        node_name = vm["node"]
        vm_id = vm["vmid"]
        routes[f"/api2/json/nodes/{node_name}/qemu/{vm_id}/config"] = generate_vm_config_route(vm)
        routes[f"/api2/json/nodes/{node_name}/qemu"].append(
            {
                "name": vm["name"],
                "maxmem": vm["maxmem"],
                "uptime": vm["uptime"],
                "vmid": vm["vmid"],
                "mem": vm["mem"],
                "disk": vm["disk"],
                "cpu": vm["cpu"],
                "maxdisk": vm["maxdisk"],
                "diskread": vm["diskread"],
                "netout": vm["netout"],
                "netin": vm["netin"],
                "diskwrite": vm["diskwrite"],
                "status": vm["status"],
                "serial": 1,
                "pid": 454971,
                "cpus": 1,
            }
        )

    return routes


def generate_vm_config_route(vm):
    if "config" in vm.keys() and vm["config"] is not None:
        return vm["config"]

    return DEFAULT_VM_CONFIG


def generate_storage_content_route(storage, storages_contents):
    def storage_content_route(_method, params=None, **_kwargs):
        items = []
        for item in storages_contents:
            storage_filter = item["volid"].split(":")[0] == storage["storage"]
            # we use in operator to check if the item content is a substring of the params content
            # ex: "image" in "images"
            content_filter = "content" not in params or item["content"] in params["content"]
            if storage_filter and content_filter:
                items.append(item)
        return items

    return storage_content_route


def generate_storages_contents_routes(nodes, storage_resources, storages_contents):
    routes = {}

    for node in nodes:
        node_name = node["status"]["name"]
        for storage in storage_resources:

            storage_name = storage["storage"]
            route = generate_storage_content_route(storage, storages_contents[node_name][storage_name])
            routes[f"/api2/json/nodes/{node_name}/storage/{storage_name}/content"] = route
    return routes


def fake_node(node_id, local=False):
    resource_id = f"node/pve-devel-{node_id}"
    name = f"pve-devel-{node_id}"
    return {
        "status": {
            "id": resource_id,
            "nodeid": node_id,
            "name": name,
            "ip": f"10.42.24.{node_id}",
            "local": 1 if local else 0,
            "type": "node",
            "online": 1,
            "level": "",
        },
        "resource": {
            "id": resource_id,
            "node": name,
            "maxmem": 202758361088,
            "disk": 20973391872,
            "mem": 4133466112,
            "uptime": 1987073,
            "maxdisk": 33601372160,
            "cpu": 0.00572599602193961,
            "type": "node",
            "status": "online",
            "level": "",
            "maxcpu": 32,
            # only in /api2/json/cluster/resources
            "cgroup-mode": 2,
            "hastate": "online",
            # only in /api2/json/nodes
            "ssl_fingerprint": ":".join(["00"] * 32),
        },
    }


def fake_vm(vm_id, node, status="running", config=None):
    return {
        "id": f"qemu/{vm_id}",
        "vmid": vm_id,
        "name": f"vm-{vm_id}",
        "node": node["status"]["name"],
        "status": status,
        "diskread": 0,
        "mem": 292823173,
        "disk": 0,
        "maxmem": 1073741824,
        "maxdisk": 2147483648,
        "uptime": 869492,
        "diskwrite": 2405421056,
        "netout": 4896058,
        "cpu": 0.00581464923852424,
        "netin": 7215771,
        "template": 0,
        "hastate": "started",
        "maxcpu": 1,
        "type": "qemu",
        "config": config,
    }


def fake_backup_job(job_id, vmid):
    return {
        "id": f"backup-d71917f0-{job_id:04x}",
        "prune-backups": {"keep-last": "3"},
        "storage": "local",
        "notes-template": "{{guestname}}",
        "schedule": "sun 01:00",
        "fleecing": {"enabled": "0"},
        "enabled": 1,
        "type": "vzdump",
        "next-run": 1735430400,
        "mode": "snapshot",
        "vmid": vmid,
        "compress": "zstd",
    }


def fake_storage_resource(name, node_name, shared=1, plugin_type="s3"):
    return {
        "content": "snippets,images,iso,backup,rootdir,vztmpl",
        "id": f"storage/{node_name}/{name}",
        "disk": 0,
        "storage": name,
        "shared": shared,
        "status": "available",
        "maxdisk": 33601372160,
        "type": "storage",
        "node": node_name,
        "plugintype": plugin_type,
    }


def fake_storage_content(storage, volid, vmid, content, ctime, storage_format, options):
    return {
        "volid": f"{storage}:{vmid}/{volid}",
        "content": content,
        "vmid": vmid,
        "ctime": ctime,
        "format": storage_format,
        "size": 1124800,
        **options,
    }


def fake_backup(storage, vmid, created_at):
    created_at_str = created_at.strftime("%Y_%m_%d-%H_%M_%S")
    volid = f"vz-dump-qemu-{vmid}-{created_at_str}.vma.zst"
    options = {
        "vmid": vmid,
        "notes": f"VM {vmid}",
        "subtype": "qemu",
    }
    return fake_storage_content(storage, volid, "backup", "backup", int(created_at.timestamp()), "vma.zst", options)
