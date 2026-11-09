from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from time import perf_counter
from urllib.parse import urlparse

import httpx

from app.config import Settings, get_settings
from app.tools.workspace import write_mission_json, write_mission_text

TEST_API_PORT = 8002
PROBE_TEAM_ID = 999001
PROBE_TEAM_NAME = "QA Probe FC"
PROBE_LEAGUE_CODE = "PL"

SENSITIVE_KEYS = {
    "password",
    "access_token",
    "token",
    "authorization",
    "jwt",
    "secret",
    "api_key",
    "apikey",
}


class UnsafeTargetError(RuntimeError):
    """La cible n'est pas la stack de test autorisée."""


@dataclass
class ProbeCheck:
    name: str
    method: str
    path: str
    expected: str
    actual: str
    passed: bool
    skipped: bool = False
    anomaly: bool = False
    duration_ms: int = 0
    detail: str = ""
    request_body: object | None = None
    response_excerpt: str = ""


@dataclass
class ProbeOutcome:
    status: str
    checks: list[ProbeCheck] = field(default_factory=list)
    anomalies: list[dict] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def ensure_test_api_url(url: str) -> None:
    """Refuse toute cible autre que la stack de test locale sur le port 8002."""
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1"}
        or parsed.port != TEST_API_PORT
    ):
        raise UnsafeTargetError(
            "Les sondes réelles sont limitées à la stack de test locale "
            f"sur le port {TEST_API_PORT}."
        )


def _redact(value):
    if isinstance(value, dict):
        return {
            key: (
                "[redacted]"
                if str(key).lower() in SENSITIVE_KEYS
                else _redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _response_excerpt(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:3000]
    return json.dumps(_redact(payload), ensure_ascii=False)[:3000]


def _validate_list_length(expected_length: int) -> Callable:
    def validator(response: httpx.Response) -> tuple[bool, str]:
        payload = response.json()
        ok = isinstance(payload, list) and len(payload) == expected_length
        return ok, f"liste de {len(payload) if isinstance(payload, list) else '?'} élément(s)"

    return validator


def _validate_non_empty_list(response: httpx.Response) -> tuple[bool, str]:
    payload = response.json()
    ok = isinstance(payload, list) and len(payload) > 0
    return ok, f"liste de {len(payload) if isinstance(payload, list) else '?'} élément(s)"


def _validate_team_57(response: httpx.Response) -> tuple[bool, str]:
    payload = response.json()
    ok = isinstance(payload, dict) and payload.get("id") == 57
    return ok, f"équipe id={payload.get('id') if isinstance(payload, dict) else '?'}"


def _validate_token(response: httpx.Response) -> tuple[bool, str]:
    payload = response.json()
    ok = isinstance(payload, dict) and bool(payload.get("access_token"))
    return ok, "jeton présent" if ok else "jeton absent"


def _validate_email(expected_email: str) -> Callable:
    def validator(response: httpx.Response) -> tuple[bool, str]:
        payload = response.json()
        actual = payload.get("email") if isinstance(payload, dict) else None
        return actual == expected_email, f"email={actual}"

    return validator


def _validate_favorite(response: httpx.Response) -> tuple[bool, str]:
    payload = response.json()
    ok = isinstance(payload, dict) and isinstance(payload.get("id"), int)
    return ok, f"favori id={payload.get('id') if isinstance(payload, dict) else '?'}"


def _validate_contains_favorite(expected_id: int) -> Callable:
    def validator(response: httpx.Response) -> tuple[bool, str]:
        payload = response.json()
        ids = {
            item.get("id")
            for item in payload
            if isinstance(item, dict)
        } if isinstance(payload, list) else set()
        return expected_id in ids, f"favori {expected_id} présent={expected_id in ids}"

    return validator


def _validate_excludes_favorite(expected_id: int) -> Callable:
    def validator(response: httpx.Response) -> tuple[bool, str]:
        payload = response.json()
        ids = {
            item.get("id")
            for item in payload
            if isinstance(item, dict)
        } if isinstance(payload, list) else set()
        return expected_id not in ids, f"favori {expected_id} présent={expected_id in ids}"

    return validator


class ApiProbe:
    """Sonde HTTP réelle, limitée à la stack de test et avec preuves locales."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client_factory: Callable[[str], httpx.Client] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client_factory = client_factory or self._default_client

    def _default_client(self, base_url: str) -> httpx.Client:
        return httpx.Client(
            base_url=base_url,
            timeout=self.settings.api_probe_timeout_seconds,
            follow_redirects=False,
        )

    def run(self, mission_id: str) -> ProbeOutcome:
        ensure_test_api_url(self.settings.test_api_url)

        base_url = self.settings.test_api_url.rstrip("/")
        checks: list[ProbeCheck] = []
        anomalies: list[dict] = []
        blocked_reason: str | None = None

        try:
            with self._client_factory(base_url) as client:
                blocked_reason = self._run_checks(
                    client, checks, anomalies
                )
        except httpx.RequestError as exc:
            blocked_reason = f"API de test injoignable ({type(exc).__name__})."
        except httpx.HTTPError as exc:
            blocked_reason = f"Erreur HTTP pendant les sondes ({type(exc).__name__})."

        status = "blocked" if blocked_reason else "completed"
        summary = self._build_summary(status, checks, anomalies, blocked_reason)

        results_path = write_mission_json(
            self.settings,
            mission_id,
            "api/probe-results.json",
            {
                "mission_id": mission_id,
                "base_url": base_url,
                "status": status,
                "blocked_reason": blocked_reason,
                "checks": [asdict(check) for check in checks],
                "anomalies": anomalies,
            },
        )
        report_path = write_mission_text(
            self.settings,
            mission_id,
            "api/probe-report.md",
            self._build_markdown(
                mission_id, base_url, status, checks, anomalies, blocked_reason
            ),
        )
        evidence = [str(results_path), str(report_path)]

        return ProbeOutcome(
            status=status,
            checks=checks,
            anomalies=anomalies,
            evidence_paths=evidence,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Exécution
    # ------------------------------------------------------------------
    def _run_checks(
        self,
        client: httpx.Client,
        checks: list[ProbeCheck],
        anomalies: list[dict],
    ) -> str | None:
        health = self._request(
            client, checks, anomalies,
            name="Santé de l'API",
            method="GET",
            path="/health",
            expected="200",
            validator=lambda r: (
                r.json().get("status") == "ok",
                f"status={r.json().get('status')}",
            ),
        )
        if health is None:
            return "API de test injoignable."

        self._request(
            client, checks, anomalies,
            name="Liste des championnats",
            method="GET",
            path="/api/football/leagues",
            expected="200 + 6 championnats",
            validator=_validate_list_length(6),
        )
        self._request(
            client, checks, anomalies,
            name="Classement Premier League",
            method="GET",
            path="/api/football/leagues/PL/standings",
            expected="200 + liste non vide",
            validator=_validate_non_empty_list,
        )
        self._request(
            client, checks, anomalies,
            name="Matchs Premier League",
            method="GET",
            path="/api/football/leagues/PL/matches",
            expected="200 + liste non vide",
            validator=_validate_non_empty_list,
        )
        self._request(
            client, checks, anomalies,
            name="Détail de l'équipe Arsenal",
            method="GET",
            path="/api/football/leagues/PL/teams/57",
            expected="200 + équipe 57",
            validator=_validate_team_57,
        )
        self._request(
            client, checks, anomalies,
            name="Championnat inconnu",
            method="GET",
            path="/api/football/leagues/XX/standings",
            expected="404",
        )

        token1 = self._login(
            client, checks, anomalies,
            name="Connexion utilisateur 1",
            email=self.settings.test_user1_email,
            password=self.settings.test_user1_password,
        )
        token2 = self._login(
            client, checks, anomalies,
            name="Connexion utilisateur 2",
            email=self.settings.test_user2_email,
            password=self.settings.test_user2_password,
        )

        if token1 is not None:
            self._request(
                client, checks, anomalies,
                name="Utilisateur courant",
                method="GET",
                path="/api/users/me",
                expected=f"200 + email {self.settings.test_user1_email}",
                token=token1,
                validator=_validate_email(self.settings.test_user1_email),
            )
        else:
            self._skip(checks, "Utilisateur courant", "connexion utilisateur 1 impossible")

        self._request(
            client, checks, anomalies,
            name="Accès sans jeton",
            method="GET",
            path="/api/users/me",
            expected="401",
        )
        self._request(
            client, checks, anomalies,
            name="Connexion avec mauvais mot de passe",
            method="POST",
            path="/api/auth/login",
            expected="401",
            json_body={
                "email": self.settings.test_user1_email,
                "password": "MotDePasseIncorrect123!",
            },
        )
        if token1 is not None:
            self._request(
                client, checks, anomalies,
                name="Inscription avec email existant",
                method="POST",
                path="/api/auth/register",
                expected="409",
                json_body={
                    "email": self.settings.test_user1_email,
                    "password": "QaTest123!",
                    "name": "QA Doublon",
                },
            )
        else:
            self._skip(
                checks,
                "Inscription avec email existant",
                "connexion utilisateur 1 impossible",
            )
        self._request(
            client, checks, anomalies,
            name="Inscription avec mot de passe trop court",
            method="POST",
            path="/api/auth/register",
            expected="422",
            json_body={
                "email": "qa.invalide@example.com",
                "password": "court",
                "name": "QA",
            },
        )

        favorite_id: int | None = None
        deleted = False
        try:
            if token1 is None:
                self._skip(checks, "Gestion des favoris", "connexion utilisateur 1 impossible")
                return None

            favorites_response = self._request(
                client, checks, anomalies,
                name="Liste des favoris utilisateur 1",
                method="GET",
                path="/api/favorites",
                expected="200 + liste",
                token=token1,
                validator=lambda r: (
                    isinstance(r.json(), list),
                    f"liste de {len(r.json()) if isinstance(r.json(), list) else '?'} élément(s)",
                ),
            )
            if favorites_response is not None:
                favorites_payload = favorites_response.json()
                if isinstance(favorites_payload, list):
                    for favorite in favorites_payload:
                        if (
                            isinstance(favorite, dict)
                            and favorite.get("team_id") == PROBE_TEAM_ID
                        ):
                            self._request(
                                client, checks, anomalies,
                                name="Nettoyage d'un favori de sonde résiduel",
                                method="DELETE",
                                path=f"/api/favorites/{favorite.get('id')}",
                                expected="204",
                                token=token1,
                            )

            created = self._request(
                client, checks, anomalies,
                name="Ajout d'un favori",
                method="POST",
                path="/api/favorites",
                expected="201 + favori créé",
                token=token1,
                json_body={
                    "team_id": PROBE_TEAM_ID,
                    "league_code": PROBE_LEAGUE_CODE,
                    "team_name": PROBE_TEAM_NAME,
                    "team_crest": "",
                },
                validator=_validate_favorite,
            )
            if created is not None and created.status_code == 201:
                favorite_id = created.json().get("id")

            self._request(
                client, checks, anomalies,
                name="Ajout en double du même favori",
                method="POST",
                path="/api/favorites",
                expected="409",
                token=token1,
                json_body={
                    "team_id": PROBE_TEAM_ID,
                    "league_code": PROBE_LEAGUE_CODE,
                    "team_name": PROBE_TEAM_NAME,
                    "team_crest": "",
                },
            )

            if favorite_id is None:
                self._skip(checks, "Isolation des favoris", "favori non créé")
            else:
                self._request(
                    client, checks, anomalies,
                    name="Le favori créé est visible par son propriétaire",
                    method="GET",
                    path="/api/favorites",
                    expected=f"200 + favori {favorite_id}",
                    token=token1,
                    validator=_validate_contains_favorite(favorite_id),
                )
                if token2 is None:
                    self._skip(checks, "Isolation des favoris", "connexion utilisateur 2 impossible")
                else:
                    self._request(
                        client, checks, anomalies,
                        name="Le favori n'est pas visible par l'autre utilisateur",
                        method="GET",
                        path="/api/favorites",
                        expected=f"200 sans favori {favorite_id}",
                        token=token2,
                        validator=_validate_excludes_favorite(favorite_id),
                    )
                    self._request(
                        client, checks, anomalies,
                        name="Suppression croisée refusée",
                        method="DELETE",
                        path=f"/api/favorites/{favorite_id}",
                        expected="404",
                        token=token2,
                    )
                self._request(
                    client, checks, anomalies,
                    name="Suppression du favori par son propriétaire",
                    method="DELETE",
                    path=f"/api/favorites/{favorite_id}",
                    expected="204",
                    token=token1,
                )
                deleted = True
                self._request(
                    client, checks, anomalies,
                    name="Le favori supprimé n'est plus listé",
                    method="GET",
                    path="/api/favorites",
                    expected=f"200 sans favori {favorite_id}",
                    token=token1,
                    validator=_validate_excludes_favorite(favorite_id),
                )
        finally:
            if favorite_id is not None and token1 is not None and not deleted:
                try:
                    client.delete(
                        f"/api/favorites/{favorite_id}",
                        headers={"Authorization": f"Bearer {token1}"},
                    )
                except httpx.HTTPError:
                    pass

        return None

    def _login(
        self,
        client: httpx.Client,
        checks: list[ProbeCheck],
        anomalies: list[dict],
        *,
        name: str,
        email: str,
        password: str,
    ) -> str | None:
        response = self._request(
            client, checks, anomalies,
            name=name,
            method="POST",
            path="/api/auth/login",
            expected="200 + jeton",
            json_body={"email": email, "password": password},
            validator=_validate_token,
        )
        if response is None or response.status_code != 200:
            return None
        try:
            return str(response.json().get("access_token") or "") or None
        except ValueError:
            return None

    def _request(
        self,
        client: httpx.Client,
        checks: list[ProbeCheck],
        anomalies: list[dict],
        *,
        name: str,
        method: str,
        path: str,
        expected: str,
        token: str | None = None,
        json_body: dict | None = None,
        validator: Callable[[httpx.Response], tuple[bool, str]] | None = None,
    ) -> httpx.Response | None:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        started = perf_counter()
        try:
            response = client.request(
                method,
                path,
                headers=headers,
                json=json_body,
            )
        except httpx.RequestError as exc:
            checks.append(
                ProbeCheck(
                    name=name,
                    method=method,
                    path=path,
                    expected=expected,
                    actual=f"connexion impossible ({type(exc).__name__})",
                    passed=False,
                    duration_ms=int((perf_counter() - started) * 1000),
                    request_body=_redact(json_body),
                )
            )
            raise

        duration_ms = int((perf_counter() - started) * 1000)
        status_match = re.match(r"\s*(\d{3})", expected)
        status_ok = (
            status_match is not None
            and response.status_code == int(status_match.group(1))
        )
        detail = ""
        body_ok = True
        if status_ok and validator is not None:
            try:
                body_ok, detail = validator(response)
            except Exception as exc:
                body_ok = False
                detail = f"validation impossible ({type(exc).__name__})"
        passed = status_ok and body_ok
        actual = f"HTTP {response.status_code}"
        if detail:
            actual += f" — {detail}"

        check = ProbeCheck(
            name=name,
            method=method,
            path=path,
            expected=expected,
            actual=actual,
            passed=passed,
            anomaly=not passed,
            duration_ms=duration_ms,
            detail=detail,
            request_body=_redact(json_body),
            response_excerpt=_response_excerpt(response),
        )
        checks.append(check)
        if not passed:
            anomalies.append(
                {
                    "check": name,
                    "method": method,
                    "path": path,
                    "expected": expected,
                    "actual": actual,
                    "reproduction": f"{method} {self.settings.test_api_url.rstrip('/')}{path}",
                    "response_excerpt": check.response_excerpt,
                }
            )
        return response

    @staticmethod
    def _skip(
        checks: list[ProbeCheck],
        name: str,
        reason: str,
    ) -> None:
        checks.append(
            ProbeCheck(
                name=name,
                method="-",
                path="-",
                expected="-",
                actual=reason,
                passed=False,
                skipped=True,
                anomaly=False,
            )
        )

    # ------------------------------------------------------------------
    # Rapports
    # ------------------------------------------------------------------
    @staticmethod
    def _build_summary(
        status: str,
        checks: list[ProbeCheck],
        anomalies: list[dict],
        blocked_reason: str | None,
    ) -> str:
        executed = [check for check in checks if not check.skipped]
        passed = [check for check in executed if check.passed]
        if status == "blocked":
            return (
                "Sondes API réelles non exécutées : "
                f"{blocked_reason or 'API de test injoignable.'} "
                "Aucune anomalie applicative n'est déclarée."
            )
        return (
            f"Sondes API réelles terminées : {len(passed)}/{len(executed)} "
            f"vérifications réussies, {len(anomalies)} anomalie(s) "
            f"reproductible(s) avec preuve."
        )

    @staticmethod
    def _build_markdown(
        mission_id: str,
        base_url: str,
        status: str,
        checks: list[ProbeCheck],
        anomalies: list[dict],
        blocked_reason: str | None,
    ) -> str:
        executed = [check for check in checks if not check.skipped]
        passed = [check for check in executed if check.passed]
        skipped = [check for check in checks if check.skipped]

        lines = [
            f"# Sondes API réelles — mission {mission_id}",
            "",
            f"- API cible : `{base_url}`",
            f"- Statut : `{status}`",
            f"- Vérifications exécutées : {len(executed)}",
            f"- Réussies : {len(passed)}",
            f"- Ignorées : {len(skipped)}",
            f"- Anomalies : {len(anomalies)}",
            "",
        ]
        if blocked_reason:
            lines.extend(
                [
                    f"> Sondes non exécutées : {blocked_reason}",
                    "",
                ]
            )

        lines.extend(
            [
                "## Vérifications",
                "",
                "| Vérification | Attendu | Obtenu | Résultat |",
                "|---|---|---|---|",
            ]
        )
        for check in checks:
            if check.skipped:
                result = "ignorée"
            elif check.passed:
                result = "réussie"
            else:
                result = "échec"
            lines.append(
                f"| {check.name} | {check.expected} | {check.actual} | {result} |"
            )

        lines.extend(["", "## Anomalies", ""])
        if not anomalies:
            lines.append(
                "Aucune anomalie : toutes les vérifications exécutées ont le "
                "résultat attendu."
            )
        else:
            for index, anomaly in enumerate(anomalies, start=1):
                lines.extend(
                    [
                        f"### {index}. {anomaly['check']}",
                        "",
                        f"- Reproduction : `{anomaly['reproduction']}`",
                        f"- Attendu : {anomaly['expected']}",
                        f"- Obtenu : {anomaly['actual']}",
                        "- Preuve de réponse :",
                        "",
                        "```json",
                        str(anomaly.get("response_excerpt", ""))[:3000],
                        "```",
                        "",
                    ]
                )
        lines.append("")
        return "\n".join(lines)
