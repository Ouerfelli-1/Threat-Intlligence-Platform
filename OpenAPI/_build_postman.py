"""Convert each <service>.openapi.json in this directory into a Postman v2.1 collection,
and emit one unified TIP-Platform collection with all services grouped by tag.

The output collections share two variables: {{baseUrl}} (default http://localhost:<port>)
and {{accessToken}} (filled by the "Login as admin" pre-request script in the unified
collection). Per-service collections set {{baseUrl}} to that service's port.

Run:
    python OpenAPI/_build_postman.py
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).parent

SERVICES = {
    "auth": 8000,
    "news-collector": 8001,
    "vuln-intel": 8002,
    "threat-intel": 8003,
    "ioc-collector": 8004,
    "threat-actors": 8005,
    "integrations": 8006,
    "cmdb": 8007,
    "flowviz": 8008,
    "asm": 8009,
    "domainwatch": 8010,
    "scheduler": 8011,
    "secrets": 8012,
    "indicator-intel": 8013,
    "orchestrator": 8014,
}


def _resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a #/components/schemas/Name reference."""
    parts = ref.lstrip("#/").split("/")
    cur = spec
    for p in parts:
        cur = cur.get(p, {})
    return cur


def _example_for_schema(schema: dict, spec: dict, depth: int = 0) -> object:
    """Generate a placeholder body matching the schema."""
    if depth > 5:
        return None
    if "$ref" in schema:
        return _example_for_schema(_resolve_ref(spec, schema["$ref"]), spec, depth + 1)
    if "anyOf" in schema:
        for opt in schema["anyOf"]:
            if opt.get("type") != "null":
                return _example_for_schema(opt, spec, depth + 1)
        return None
    if "allOf" in schema:
        merged: dict = {}
        for opt in schema["allOf"]:
            sub = _example_for_schema(opt, spec, depth + 1)
            if isinstance(sub, dict):
                merged.update(sub)
        return merged

    t = schema.get("type")
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]

    if t == "object" or "properties" in schema:
        out: dict = {}
        for prop, sub in (schema.get("properties") or {}).items():
            out[prop] = _example_for_schema(sub, spec, depth + 1)
        return out
    if t == "array":
        item = schema.get("items") or {}
        return [_example_for_schema(item, spec, depth + 1)]
    if t == "string":
        fmt = schema.get("format", "")
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt == "date-time":
            return "2026-01-01T00:00:00Z"
        if fmt == "date":
            return "2026-01-01"
        if fmt == "email":
            return "user@example.com"
        return "string"
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return False
    return None


def _path_to_postman_url(path: str, base_var: str = "baseUrl") -> dict:
    # Turn /assets/{id} into ["{{baseUrl}}","assets",":id"]
    parts = []
    variables = []
    for seg in path.strip("/").split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            name = seg[1:-1]
            parts.append(":" + name)
            variables.append({"key": name, "value": ""})
        elif seg:
            parts.append(seg)
    return {
        "raw": "{{" + base_var + "}}" + path,
        "host": ["{{" + base_var + "}}"],
        "path": parts,
        "variable": variables,
    }


def _build_request(method: str, path: str, op: dict, spec: dict, base_var: str = "baseUrl") -> dict:
    name = op.get("summary") or op.get("operationId") or f"{method.upper()} {path}"

    headers = [
        {"key": "Authorization", "value": "Bearer {{accessToken}}", "type": "text"},
    ]
    body = None
    request_body = op.get("requestBody") or {}
    content = (request_body.get("content") or {})
    json_schema = content.get("application/json", {}).get("schema")
    if json_schema:
        headers.append({"key": "Content-Type", "value": "application/json", "type": "text"})
        example = _example_for_schema(json_schema, spec)
        body = {
            "mode": "raw",
            "raw": json.dumps(example, indent=2, default=str),
            "options": {"raw": {"language": "json"}},
        }

    # Query parameters
    url = _path_to_postman_url(path, base_var)
    params = op.get("parameters") or []
    queries = []
    for p in params:
        if p.get("in") == "query":
            queries.append({
                "key": p.get("name", ""),
                "value": "",
                "description": p.get("description", ""),
                "disabled": not p.get("required", False),
            })
    if queries:
        url["query"] = queries

    description = op.get("description") or op.get("summary") or ""
    item = {
        "name": name,
        "request": {
            "method": method.upper(),
            "header": headers,
            "url": url,
            "description": description,
        },
        "response": [],
    }
    if body:
        item["request"]["body"] = body
    return item


def _collection_from_spec(spec: dict, name: str, port: int, base_var: str = "baseUrl") -> dict:
    """Convert one OpenAPI spec → Postman v2.1 collection grouped by tag."""
    tag_buckets: dict[str, list[dict]] = {}
    for path, methods in (spec.get("paths") or {}).items():
        for method, op in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            tags = op.get("tags") or ["default"]
            tag = tags[0]
            tag_buckets.setdefault(tag, []).append(_build_request(method, path, op, spec, base_var))

    items = []
    for tag in sorted(tag_buckets):
        items.append({
            "name": tag,
            "item": tag_buckets[tag],
        })

    info = spec.get("info") or {}
    return {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": f"TIP — {name}",
            "description": info.get("description") or info.get("title", name),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
        "variable": [
            {"key": base_var, "value": f"http://localhost:{port}", "type": "string"},
            {"key": "accessToken", "value": "", "type": "string"},
        ],
    }


PRE_REQUEST_LOGIN = r"""
// TIP — auto-login as admin if accessToken is empty.
// Set {{adminUsername}} and {{adminPassword}} as collection / environment variables.
(function () {
    if (pm.variables.get("accessToken")) return;
    var authBase = pm.variables.get("authUrl") || "http://localhost:8000";
    pm.sendRequest({
        url: authBase + "/login",
        method: "POST",
        header: { "Content-Type": "application/json" },
        body: { mode: "raw", raw: JSON.stringify({
            username: pm.variables.get("adminUsername") || "admin",
            password: pm.variables.get("adminPassword") || "changeme",
        })},
    }, function (err, res) {
        if (err) { console.log("login error", err); return; }
        if (res && res.json && res.json().access_token) {
            pm.variables.set("accessToken", res.json().access_token);
            console.log("TIP: access token cached");
        } else {
            console.log("TIP login failed", res && res.text());
        }
    });
})();
"""


def _unified_collection(per_service: dict[str, dict]) -> dict:
    folders = []
    for service, port in SERVICES.items():
        coll = per_service[service]
        # Re-host items to use a per-service base var (e.g. {{baseUrlAuth}})
        var_name = "baseUrl" + service.replace("-", "").title().replace(" ", "")
        var_name = re.sub(r"[^A-Za-z0-9]", "", var_name)
        sub_items = []
        for tag_folder in coll["item"]:
            new_tag = {"name": tag_folder["name"], "item": []}
            for req in tag_folder["item"]:
                req_copy = json.loads(json.dumps(req))
                url = req_copy["request"]["url"]
                url["raw"] = url["raw"].replace("{{baseUrl}}", "{{" + var_name + "}}")
                url["host"] = ["{{" + var_name + "}}"]
                new_tag["item"].append(req_copy)
            sub_items.append(new_tag)

        folders.append({
            "name": f"{service} ({port})",
            "description": coll["info"]["description"],
            "item": sub_items,
        })

    variables = [
        {"key": "authUrl", "value": "http://localhost:8000", "type": "string"},
        {"key": "accessToken", "value": "", "type": "string"},
        {"key": "adminUsername", "value": "admin", "type": "string"},
        {"key": "adminPassword", "value": "changeme", "type": "string"},
    ]
    for service, port in SERVICES.items():
        var_name = "baseUrl" + service.replace("-", "").title().replace(" ", "")
        var_name = re.sub(r"[^A-Za-z0-9]", "", var_name)
        variables.append({"key": var_name, "value": f"http://localhost:{port}", "type": "string"})

    return {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": "TIP Platform — Unified Collection",
            "description": (
                "Every endpoint of every TIP service in one place.\n\n"
                "**Auth flow**: a pre-request script on the root folder calls POST /login on "
                "{{authUrl}} with {{adminUsername}} / {{adminPassword}} and caches the access "
                "token in {{accessToken}}. All requests use it automatically.\n\n"
                "**Hosts**: each service has its own {{baseUrlXxx}} variable. Edit them once "
                "for remote deploys (e.g. http://lightserv1.local:8000)."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{accessToken}}", "type": "string"}],
        },
        "event": [
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": PRE_REQUEST_LOGIN.splitlines(),
                },
            }
        ],
        "item": folders,
        "variable": variables,
    }


def main() -> None:
    per_service: dict[str, dict] = {}
    for service, port in SERVICES.items():
        spec_path = ROOT / f"{service}.openapi.json"
        if not spec_path.exists():
            print(f"skip {service}: no spec")
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        coll = _collection_from_spec(spec, service, port)
        per_service[service] = coll
        out = ROOT / "postman" / f"{service}.postman_collection.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(coll, indent=2), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT.parent)}")

    if per_service:
        unified = _unified_collection(per_service)
        out = ROOT / "postman" / "_unified.postman_collection.json"
        out.write_text(json.dumps(unified, indent=2), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
