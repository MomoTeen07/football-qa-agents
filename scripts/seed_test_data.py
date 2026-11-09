"""Crée les comptes de test dans la base de test isolée.

Ce script ne doit être exécuté que contre la stack de test (port 8002).
Il ne touche jamais à la base réelle.
"""

from __future__ import annotations

import os
import sys

import requests

API_URL = os.getenv("TEST_API_URL", "http://localhost:8002")
USERS = [
    (
        os.getenv("TEST_USER1_EMAIL", "qa.user1@example.com"),
        os.getenv("TEST_USER1_PASSWORD", "QaTest123!"),
        "QA User One",
    ),
    (
        os.getenv("TEST_USER2_EMAIL", "qa.user2@example.com"),
        os.getenv("TEST_USER2_PASSWORD", "QaTest123!"),
        "QA User Two",
    ),
]


def request(method: str, path: str, **kwargs) -> requests.Response:
    response = requests.request(method, f"{API_URL}{path}", timeout=10, **kwargs)
    return response


def ensure_user(email: str, password: str, name: str) -> str:
    response = request(
        "POST",
        "/api/auth/register",
        json={"email": email, "password": password, "name": name},
    )
    if response.status_code == 409:
        response = request(
            "POST",
            "/api/auth/login",
            json={"email": email, "password": password},
        )
    response.raise_for_status()
    token = response.json()["access_token"]
    me = request("GET", "/api/users/me", headers={"Authorization": f"Bearer {token}"})
    me.raise_for_status()
    print(f"OK  {email} -> {me.json()['name']}")
    return token


def main() -> int:
    try:
        health = request("GET", "/health")
        health.raise_for_status()
    except requests.RequestException as exc:
        print(f"ERREUR : stack de test inaccessible sur {API_URL} : {exc}", file=sys.stderr)
        return 1

    for email, password, name in USERS:
        ensure_user(email, password, name)

    print("Comptes de test prêts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
