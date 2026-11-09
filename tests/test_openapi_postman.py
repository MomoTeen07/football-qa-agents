from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.tools.openapi_postman import (
    analyze_openapi,
    build_postman_collection,
    build_postman_environment,
    write_postman_assets,
)

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Football QA API", "version": "1.0.0"},
    "paths": {
        "/health": {
            "get": {
                "summary": "Health",
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/api/users/me": {
            "get": {
                "tags": ["users"],
                "summary": "Current user",
                "security": [{"HTTPBearer": []}],
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/api/favorites": {
            "post": {
                "tags": ["favorites"],
                "summary": "Add favorite",
                "security": [{"HTTPBearer": []}],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/FavoriteCreate"}
                        }
                    }
                },
                "responses": {"201": {"description": "Created"}},
            }
        },
        "/api/football/leagues/{code}/teams/{team_id}": {
            "get": {
                "tags": ["football"],
                "summary": "Team",
                "parameters": [
                    {"name": "code", "in": "path", "required": True},
                    {"name": "team_id", "in": "path", "required": True},
                ],
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
    "components": {
        "schemas": {
            "FavoriteCreate": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "integer"},
                    "team_name": {"type": "string"},
                },
            }
        }
    },
}


def _items(collection: dict) -> dict[str, dict]:
    return {folder["name"]: folder for folder in collection["item"]}


def test_analysis_counts_operations_and_bearer() -> None:
    analysis = analyze_openapi(SPEC)

    assert analysis["operation_count"] == 4
    assert "FavoriteCreate" in analysis["schemas"]
    me = next(
        operation
        for operation in analysis["operations"]
        if operation["path"] == "/api/users/me"
    )
    assert me["requires_bearer"] is True


def test_collection_contains_real_requests_and_tests() -> None:
    collection = build_postman_collection(SPEC, "http://localhost:8002")
    folders = _items(collection)

    assert set(folders) == {"health", "users", "favorites", "football"}
    assert [folder["name"] for folder in collection["item"]] == [
        "health",
        "users",
        "favorites",
        "football",
    ]

    health = folders["health"]["item"][0]
    assert health["request"]["method"] == "GET"
    assert health["request"]["url"]["raw"] == "{{baseUrl}}/health"
    assert any(
        "pm.response.to.have.status(200)" in line
        for line in health["event"][0]["script"]["exec"]
    )

    me = folders["users"]["item"][0]
    headers = {item["key"]: item["value"] for item in me["request"]["header"]}
    assert headers["Authorization"] == "Bearer {{token}}"

    favorite = folders["favorites"]["item"][0]
    body = json.loads(favorite["request"]["body"]["raw"])
    assert body["team_id"] == 57
    assert body["league_code"] == "PL"
    assert any(
        'pm.collectionVariables.set("favoriteId"' in line
        for line in favorite["event"][0]["script"]["exec"]
    )

    team = folders["football"]["item"][0]
    assert team["request"]["url"]["raw"] == (
        "{{baseUrl}}/api/football/leagues/{{code}}/teams/{{team_id}}"
    )
    variables = {
        item["key"]: item["value"]
        for item in team["request"]["url"]["variable"]
    }
    assert variables == {"code": "PL", "team_id": "57"}


def test_environment_and_written_assets(tmp_path: Path) -> None:
    environment = build_postman_environment(
        "http://localhost:8002",
        test_user_email="qa.user1@example.com",
        test_user_password="QaTest123!",
    )
    values = {item["key"]: item["value"] for item in environment["values"]}
    assert values["baseUrl"] == "http://localhost:8002"
    assert values["testUserEmail"] == "qa.user1@example.com"
    assert values["token"] == ""

    settings = Settings(
        _env_file=None,
        postman_dir=tmp_path / "postman",
    )
    collection_path, environment_path = write_postman_assets(
        settings,
        build_postman_collection(SPEC, "http://localhost:8002"),
        environment,
    )

    assert collection_path.is_file()
    assert environment_path.is_file()
    assert collection_path.name == "football-qa.json"
    assert environment_path.name == "football-qa-test.json"
