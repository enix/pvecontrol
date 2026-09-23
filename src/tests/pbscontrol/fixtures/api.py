import json
import requests
import responses

PBS_BASE_URL = "https://host:8007"


def execute_route(routes, method, url, **kwargs):
    print(f"{method} {url}")
    print(f"params: {kwargs.get('params', {})}")
    path = url.replace(PBS_BASE_URL, "")
    assert path in routes, f"Route not found: {path}\nAvailable routes: {list(routes.keys())}"

    route = routes[path]
    data = route(method, **kwargs) if callable(route) else route

    content = json.dumps({"data": data})
    print(content + "\n")

    return content


def create_response_wrapper(datastores):
    routes = generate_routes(datastores)

    def wrapper(path, data=None, **kwargs):
        kwargs["params"] = kwargs.get("params", {})
        url = PBS_BASE_URL + path

        if data is None:
            body = execute_route(routes, "GET", url, **kwargs)
        else:
            body = json.dumps({"data": data})

        responses.get(url, body=body)

    return wrapper


def generate_routes(datastores):
    routes = {
        "/api2/json/version": {"version": "4.1.1", "release": "4.1", "repoid": "aabbccdd"},
        "/api2/json/admin/datastore": [{"store": ds["store"], "path": ds["path"]} for ds in datastores],
        **generate_datastore_status_routes(datastores),
    }

    print("ROUTES:")
    for route_path in routes.keys():
        print(route_path)
    print("")

    return routes


def generate_datastore_status_routes(datastores):
    return {
        f"/api2/json/admin/datastore/{ds['store']}/status": {
            "total": ds["total"],
            "used": ds["used"],
            "avail": ds["avail"],
            "gc-status": ds.get("gc-status", {"upid": None}),
        }
        for ds in datastores
    }


def fake_datastore(name, total=1_000_000_000_000, used=400_000_000_000, gc_error=None):
    avail = total - used
    gc_status = {"error": gc_error} if gc_error else {"upid": None}
    return {
        "store": name,
        "path": f"/mnt/datastore/{name}",
        "total": total,
        "used": used,
        "avail": avail,
        "gc-status": gc_status,
    }
