from __future__ import annotations

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx

from app.config import Settings

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

FOLDER_ORDER = {
    "health": 0,
    "auth": 1,
    "users": 2,
    "favorites": 3,
    "football": 4,
    "default": 99,
}

PATH_EXAMPLES = {
    "code": "PL",
    "team_id": 57,
    "favorite_id": "{{favoriteId}}",
}

BODY_EXAMPLES = {
    ("/api/auth/register", "POST"): {
        "email": "qa.nouveau@example.com",
        "password": "QaTest123!",
        "name": "QA Nouveau",
    },
    ("/api/auth/login", "POST"): {
        "email": "{{testUserEmail}}",
        "password": "{{testUserPassword}}",
    },
    ("/api/favorites", "POST"): {
        "team_id": 57,
        "league_code": "PL",
        "team_name": "Arsenal",
        "team_crest": "",
    },
}


def fetch_openapi(base_url: str, *, timeout: float = 20.0) -> dict:
    response = httpx.get(
        f"{base_url.rstrip('/')}/openapi.json",
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def iter_operations(spec: dict):
    for path, item in spec.get("paths", {}).items():
        for method, operation in item.items():
            if method.lower() in HTTP_METHODS and isinstance(operation, dict):
                yield path, method.upper(), operation


def analyze_openapi(spec: dict) -> dict:
    operations = list(iter_operations(spec))
    return {
        "title": spec.get("info", {}).get("title", "API"),
        "version": spec.get("info", {}).get("version", ""),
        "operation_count": len(operations),
        "operations": [
            {
                "method": method,
                "path": path,
                "summary": operation.get("summary", ""),
                "requires_bearer": _requires_bearer(spec, operation),
            }
            for path, method, operation in operations
        ],
        "schemas": sorted(
            spec.get("components", {}).get("schemas", {}).keys()
        ),
    }


def build_postman_collection(spec: dict, base_url: str) -> dict:
    folders: dict[str, list[dict]] = {}
    for path, method, operation in iter_operations(spec):
        tags = operation.get("tags") or []
        if tags:
            folder_name = str(tags[0])
        elif path == "/health":
            folder_name = "health"
        else:
            folder_name = "default"
        folders.setdefault(folder_name, []).append(
            _build_item(spec, base_url, path, method, operation)
        )

    items = [
        {"name": name, "item": folders[name]}
        for name in sorted(
            folders,
            key=lambda value: (FOLDER_ORDER.get(value.lower(), 50), value),
        )
    ]

    return {
        "info": {
            "name": "Football QA API — test",
            "description": (
                "Collection générée depuis l'OpenAPI réel de la stack de test "
                f"({base_url}). Variables : baseUrl, token, favoriteId, "
                "testUserEmail, testUserPassword."
            ),
            "schema": (
                "https://schema.getpostman.com/json/collection/v2.1.0/"
                "collection.json"
            ),
        },
        "variable": [
            {"key": "baseUrl", "value": base_url, "type": "default"},
            {"key": "token", "value": "", "type": "secret"},
            {"key": "favoriteId", "value": "", "type": "default"},
        ],
        "item": items,
    }


def build_postman_environment(
    base_url: str,
    *,
    test_user_email: str,
    test_user_password: str,
) -> dict:
    return {
        # Identifiant stable : un UUID aléatoire salissait le dépôt à chaque
        # mission (l'environnement Postman est versionné).
        "id": str(uuid5(NAMESPACE_URL, "football-qa-agents/environment/football-qa-test")),
        "name": "Football QA — test (8002)",
        "_postman_variable_scope": "environment",
        "values": [
            {
                "key": "baseUrl",
                "value": base_url,
                "type": "default",
                "enabled": True,
            },
            {
                "key": "testUserEmail",
                "value": test_user_email,
                "type": "default",
                "enabled": True,
            },
            {
                "key": "testUserPassword",
                "value": test_user_password,
                "type": "default",
                "enabled": True,
            },
            {"key": "token", "value": "", "type": "secret", "enabled": True},
            {
                "key": "favoriteId",
                "value": "",
                "type": "default",
                "enabled": True,
            },
        ],
    }


def write_postman_assets(
    settings: Settings,
    collection: dict,
    environment: dict,
) -> tuple[Path, Path]:
    collection_path = (
        Path(settings.postman_dir) / "collections" / "football-qa.json"
    )
    environment_path = (
        Path(settings.postman_dir) / "environments" / "football-qa-test.json"
    )
    collection_path.parent.mkdir(parents=True, exist_ok=True)
    environment_path.parent.mkdir(parents=True, exist_ok=True)
    collection_path.write_text(
        json.dumps(collection, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    environment_path.write_text(
        json.dumps(environment, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return collection_path, environment_path


def _build_item(
    spec: dict,
    base_url: str,
    path: str,
    method: str,
    operation: dict,
) -> dict:
    requires_bearer = _requires_bearer(spec, operation)
    headers = [{"key": "Accept", "value": "application/json"}]
    body = _request_body(path, method, operation, spec)
    if body is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})
    if requires_bearer:
        headers.append(
            {"key": "Authorization", "value": "Bearer {{token}}"}
        )

    request: dict = {
        "method": method,
        "header": headers,
        "url": _build_url(base_url, path, operation),
        "description": operation.get("description")
        or operation.get("summary", ""),
    }
    if body is not None:
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2, ensure_ascii=False),
            "options": {"raw": {"language": "json"}},
        }

    return {
        "name": operation.get("summary") or f"{method} {path}",
        "request": request,
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": _test_script(path, method, operation),
                },
            }
        ],
    }


def _build_url(base_url: str, path: str, operation: dict) -> dict:
    segments: list[str] = []
    variables: list[dict] = []
    for segment in [part for part in path.split("/") if part]:
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            example = PATH_EXAMPLES.get(name, "value")
            segments.append(f"{{{{{name}}}}}")
            variables.append({"key": name, "value": str(example)})
        else:
            segments.append(segment)

    url: dict = {
        "raw": "{{baseUrl}}/" + "/".join(segments),
        "host": ["{{baseUrl}}"],
        "path": segments,
    }
    if variables:
        url["variable"] = variables

    query = []
    for parameter in operation.get("parameters", []):
        if parameter.get("in") != "query":
            continue
        schema = parameter.get("schema") or {}
        query.append(
            {
                "key": parameter.get("name", ""),
                "value": str(schema.get("example", "")),
                "disabled": not parameter.get("required", False),
            }
        )
    if query:
        url["query"] = query
    return url


def _request_body(
    path: str,
    method: str,
    operation: dict,
    spec: dict,
) -> dict | None:
    example = BODY_EXAMPLES.get((path, method))
    if example is not None:
        return example

    request_body = operation.get("requestBody") or {}
    content = request_body.get("content") or {}
    media = content.get("application/json") or {}
    schema = _resolve_schema(media.get("schema") or {}, spec)
    if not schema:
        return None
    if "example" in schema:
        return schema["example"]
    properties = schema.get("properties") or {}
    if not properties:
        return None
    result = {}
    for name, prop in properties.items():
        prop = _resolve_schema(prop, spec)
        result[name] = prop.get(
            "example",
            prop.get("default", _value_for_type(prop)),
        )
    return result


def _resolve_schema(schema: dict, spec: dict) -> dict:
    if not isinstance(schema, dict):
        return {}
    if "$ref" not in schema:
        return schema
    name = schema["$ref"].split("/")[-1]
    return spec.get("components", {}).get("schemas", {}).get(name, {})


def _value_for_type(schema: dict):
    kind = schema.get("type")
    if kind == "integer":
        return 1
    if kind == "number":
        return 1.0
    if kind == "boolean":
        return True
    if kind == "array":
        return []
    if kind == "object":
        return {}
    return "value"


def _requires_bearer(spec: dict, operation: dict) -> bool:
    security = operation.get("security")
    if security is None:
        security = spec.get("security") or []
    for requirement in security:
        if "HTTPBearer" in requirement:
            return True
    return False


def _success_status(operation: dict) -> int:
    for code in sorted((operation.get("responses") or {}).keys()):
        if str(code).startswith("2"):
            return int(code)
    return 200


def _test_script(path: str, method: str, operation: dict) -> list[str]:
    success = _success_status(operation)
    lines = [
        f'pm.test("Statut attendu {success}", function () {{',
        f"    pm.response.to.have.status({success});",
        "});",
    ]
    if success != 204:
        lines.extend(
            [
                'pm.test("Réponse JSON", function () {',
                "    pm.response.to.be.json;",
                "});",
            ]
        )
    if path in {"/api/auth/login", "/api/auth/register"} and method == "POST":
        lines.extend(
            [
                "const data = pm.response.json();",
                "if (data.access_token) {",
                '    pm.collectionVariables.set("token", data.access_token);',
                "}",
            ]
        )
    if path == "/api/favorites" and method == "POST":
        lines.extend(
            [
                "const favorite = pm.response.json();",
                "if (favorite.id) {",
                '    pm.collectionVariables.set("favoriteId", favorite.id);',
                "}",
            ]
        )
    return lines
