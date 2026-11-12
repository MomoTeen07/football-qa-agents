from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.agents.phase7 import DEVOPS_FALLBACK, DevOpsAgent, QAReporterAgent
from app.config import Settings
from app.domain.models import Mission, Task
from app.orchestrator.planner import build_plan, mission_requires_approval
from app.tools.devops import DevOpsOutcome, DevOpsPromotion


def make_settings(
    tmp_path: Path,
    *,
    real_agents_enabled: bool = True,
    publish: bool = False,
) -> Settings:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    return Settings(
        _env_file=None,
        real_agents_enabled=real_agents_enabled,
        workspace_dir=tmp_path / "workspace",
        reports_dir=tmp_path / "reports" / "missions",
        allure_results_dir=tmp_path / "reports" / "allure-results",
        postman_dir=tmp_path / "postman",
        devops_repo_dir=repo,
        devops_publish_enabled=publish,
        test_api_url="http://localhost:8002",
        test_ui_url="http://localhost:5175",
        test_user1_password="QaTest123!",
        test_user2_password="QaTest123!",
    )


def make_mission() -> Mission:
    return Mission(instruction="Prépare une branche et une pull request.")


def make_task(mission: Mission, agent: str = "devops") -> Task:
    return Task(
        mission_id=mission.id,
        key=agent,
        agent=agent,
        title=f"Tâche {agent}",
    )


def write_sources(settings: Settings, mission_id: str) -> Path:
    base = settings.workspace_dir / "missions" / mission_id
    (base / "api-automation").mkdir(parents=True, exist_ok=True)
    (base / "api-automation" / "test_api_suite.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    (base / "ui-automation").mkdir(parents=True, exist_ok=True)
    (base / "ui-automation" / "run_ui_checks.py").write_text(
        "print('ok')\n", encoding="utf-8"
    )
    return base


class FakeGitRunner:
    def __init__(
        self,
        repo_root: Path,
        *,
        dirty: bool = False,
        branch_exists: bool = False,
        push_failure: bool = False,
        pr_failure: bool = False,
        fetch_stderr: str = "",
    ) -> None:
        self.repo_root = repo_root
        self.dirty = dirty
        self.branch_exists = branch_exists
        self.push_failure = push_failure
        self.pr_failure = pr_failure
        self.fetch_stderr = fetch_stderr
        self.calls: list[list[str]] = []

    def __call__(
        self, command: list[str], cwd: Path
    ) -> subprocess.CompletedProcess:
        self.calls.append(list(command))

        def done(
            code: int = 0, stdout: str = "", stderr: str = ""
        ) -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(command, code, stdout, stderr)

        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return done(stdout=str(self.repo_root))
        if command[:3] == ["git", "rev-parse", "--verify"]:
            return done(0 if self.branch_exists else 1)
        if command == ["git", "rev-parse", "HEAD"]:
            return done(stdout="abc123")
        if command[:2] == ["git", "branch"]:
            return done(stdout="main")
        if command[:2] == ["git", "status"]:
            return done(stdout=" M src/app.py\n" if self.dirty else "")
        if command[:2] == ["git", "fetch"]:
            return done(
                1 if self.fetch_stderr else 0,
                stderr=self.fetch_stderr,
            )
        if command[:2] == ["git", "switch"]:
            return done()
        if command[:2] == ["git", "add"]:
            return done()
        if command[:2] == ["git", "commit"]:
            return done(stdout="[branch abc123] message")
        if command[:2] == ["git", "push"]:
            return done(
                1 if self.push_failure else 0,
                stderr="rejected" if self.push_failure else "",
            )
        if command[:2] == ["gh", "pr"]:
            return done(
                1 if self.pr_failure else 0,
                stdout=(
                    ""
                    if self.pr_failure
                    else "https://github.com/example/repo/pull/1\n"
                ),
                stderr="gh: authentication required" if self.pr_failure else "",
            )
        return done()


class ForbiddenPromotion:
    def run(self, mission_id: str, *, publish: bool | None = None):
        raise AssertionError("la promotion ne doit pas être exécutée en repli")


def find_command(
    commands: list[list[str]], prefix: tuple[str, ...]
) -> list[str]:
    return next(
        command for command in commands if tuple(command[: len(prefix)]) == prefix
    )


def test_devops_uses_fallback_without_real_agents(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, real_agents_enabled=False)
    mission = make_mission()

    result = DevOpsAgent(
        settings, promotion=ForbiddenPromotion()  # type: ignore[arg-type]
    ).run(make_task(mission), mission)

    assert result.summary == DEVOPS_FALLBACK
    assert result.evidence == []
    assert result.artifacts == ["branche + PR (déterministe)"]


def test_devops_dry_run_does_not_touch_the_repository(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "planned"
    assert outcome.branch == f"qa/promotion-{mission.id}"
    assert len(outcome.promoted_files) == 3
    destination = (
        settings.devops_repo_dir
        / "tests"
        / "generated"
        / mission.id
    )
    assert not destination.exists()
    for command in runner.calls:
        assert tuple(command[:2]) not in {
            ("git", "fetch"),
            ("git", "switch"),
            ("git", "add"),
            ("git", "commit"),
            ("git", "push"),
            ("gh", "pr"),
        }
    assert Path(outcome.evidence_paths[0]).is_file()
    assert Path(outcome.evidence_paths[1]).is_file()


def test_devops_refuses_without_generated_tests(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    runner = FakeGitRunner(settings.devops_repo_dir)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "blocked"
    assert "Aucun test généré" in (outcome.blocked_reason or "")
    assert runner.calls == []
    assert Path(outcome.evidence_paths[0]).is_file()


def test_devops_refuses_dirty_worktree(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, publish=True)
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir, dirty=True)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "blocked"
    assert "Arbre de travail non propre" in (outcome.blocked_reason or "")
    assert not any(command[:2] == ["git", "switch"] for command in runner.calls)
    assert not any(command[:2] == ["git", "push"] for command in runner.calls)


def test_devops_publishes_branch_and_pull_request(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, publish=True)
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "completed"
    assert outcome.branch == f"qa/promotion-{mission.id}"
    assert outcome.commit == "abc123"
    assert outcome.pr_url == "https://github.com/example/repo/pull/1"

    destination = (
        settings.devops_repo_dir
        / "tests"
        / "generated"
        / mission.id
    )
    assert (destination / "test_api_suite.py").is_file()
    assert (destination / "run_ui_checks.py").is_file()
    manifest = json.loads(
        (destination / "promotion.json").read_text(encoding="utf-8")
    )
    assert manifest["mission_id"] == mission.id
    assert manifest["files"] == ["test_api_suite.py", "run_ui_checks.py"]

    switch = find_command(runner.calls, ("git", "switch"))
    assert switch[-1] == "origin/main"
    push = find_command(runner.calls, ("git", "push"))
    assert push == ["git", "push", "-u", "origin", outcome.branch]
    assert "main" not in push
    pr = find_command(runner.calls, ("gh", "pr"))
    assert pr[2] == "create"
    assert "--base" in pr and "main" in pr
    assert "--head" in pr and outcome.branch in pr
    for command in runner.calls:
        assert "--force" not in command
        assert "-f" not in command


def test_devops_refuses_existing_branch(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, publish=True)
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir, branch_exists=True)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "blocked"
    assert "existe déjà" in (outcome.blocked_reason or "")
    assert not any(command[:2] == ["git", "switch"] for command in runner.calls)


def test_devops_push_failure_keeps_local_branch(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, publish=True)
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir, push_failure=True)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "blocked"
    assert outcome.commit == "abc123"
    assert "Push de la branche impossible" in (outcome.blocked_reason or "")
    assert not any(command[:2] == ["gh", "pr"] for command in runner.calls)


def test_devops_pr_failure_reports_blocked(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, publish=True)
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir, pr_failure=True)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "blocked"
    assert outcome.commit == "abc123"
    assert outcome.pr_url is None
    assert "pull request non créée" in (outcome.blocked_reason or "")


def test_devops_agent_exposes_real_outcome(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    outcome = DevOpsOutcome(
        status="completed",
        branch="qa/promotion-x",
        commit="abc123",
        pr_url="https://github.com/example/repo/pull/2",
        promoted_files=["tests/generated/x/test_api_suite.py"],
        summary="Promotion publiée.",
        evidence_paths=["devops/devops-results.json"],
    )

    class FakePromotion:
        def run(self, mission_id: str, *, publish: bool | None = None):
            return outcome

    result = DevOpsAgent(settings, promotion=FakePromotion()).run(  # type: ignore[arg-type]
        make_task(mission), mission
    )

    assert "Promotion publiée." in result.summary
    assert "qa/promotion-x" in result.summary
    assert "https://github.com/example/repo/pull/2" in result.summary
    assert result.artifacts == ["https://github.com/example/repo/pull/2"]
    assert result.evidence == ["devops/devops-results.json"]


def write_payloads(settings: Settings, mission_id: str) -> None:
    base = settings.workspace_dir / "missions" / mission_id
    payloads = {
        "api/probe-results.json": {
            "status": "completed",
            "base_url": "http://localhost:8002",
            "checks": [
                {
                    "name": "Santé de l'API",
                    "method": "GET",
                    "path": "/health",
                    "expected": "200",
                    "actual": "HTTP 200",
                    "passed": True,
                    "skipped": False,
                    "duration_ms": 5,
                    "detail": "status=ok",
                    "response_excerpt": '{"status": "ok"}',
                }
            ],
            "anomalies": [],
        },
        "api-automation/api-automation-results.json": {
            "status": "completed",
            "base_url": "http://localhost:8002",
            "summary": {
                "tests": 1,
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "anomalies": 0,
            },
            "checks": [
                {
                    "name": "test_health",
                    "outcome": "passed",
                    "duration_s": 0.1,
                    "detail": "",
                }
            ],
            "anomalies": [],
        },
        "ui-automation/ui-automation-results.json": {
            "status": "completed",
            "ui_url": "http://localhost:5175",
            "summary": {
                "checks": 1,
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "anomalies": 0,
            },
            "checks": [
                {
                    "name": "Accueil",
                    "status": "passed",
                    "expected": "h1 visible",
                    "detail": "",
                    "path": "/",
                    "duration_s": 0.2,
                    "screenshot": "",
                }
            ],
            "anomalies": [],
        },
    }
    for relative, payload in payloads.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )


def test_reporter_generates_allure_and_json_report(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    write_payloads(settings, mission.id)
    task = make_task(mission, "qa_reporter")

    result = QAReporterAgent(settings).run(
        task,
        mission,
        context={
            "tasks": [
                {
                    "agent": "api_tester",
                    "title": "API",
                    "status": "completed",
                    "result": "Sondes terminées",
                    "evidence": [],
                }
            ]
        },
    )

    assert "## Synthèse globale" in result.summary
    assert "## Rapport Allure" in result.summary
    assert "Résultats Allure 2" in result.summary
    assert "Aucune anomalie déclarée" in result.summary

    json_path = settings.reports_dir / f"{mission.id}.json"
    assert json_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["mission_id"] == mission.id
    assert payload["allure"]["status"] == "completed"
    assert payload["allure"]["total"] == 3

    results_dir = (
        settings.allure_results_dir / mission.id
    )
    assert len(list(results_dir.glob("*-result.json"))) == 3
    assert str(json_path) in result.evidence
    assert str(results_dir) in result.evidence
    assert result.artifacts == [str(results_dir)]


def test_reporter_without_results_skips_allure(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    mission = make_mission()
    task = make_task(mission, "qa_reporter")

    result = QAReporterAgent(settings).run(task, mission, context={"tasks": []})

    assert "Aucun test réel n'a été exécuté" in result.summary
    assert "aucun résultat Allure généré" in result.summary
    assert not (settings.allure_results_dir / mission.id).exists()
    assert result.artifacts == []
    assert len(result.evidence) == 1
    assert Path(result.evidence[0]).is_file()


def test_devops_instruction_requires_explicit_approval() -> None:
    required, reason = mission_requires_approval(
        "Prépare une branche Git et une pull request pour les tests générés."
    )
    assert required is True
    assert reason is not None and "branche" in reason

    plan = build_plan(
        "Prépare une branche Git et une pull request pour les tests générés."
    )
    assert any(item["agent"] == "devops" for item in plan)

    required, reason = mission_requires_approval("Analyse l'application.")
    assert required is False
    assert reason is None


# ----------------------------------------------------------------------
# Garde-fous DevOps renforcés (phase 9, WP4)
# ----------------------------------------------------------------------
SENTINEL = "sentinel-phase9-do-not-leak-7f21"


def test_devops_commands_are_bounded_lists_without_force(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, publish=True)
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "completed"
    for command in runner.calls:
        assert isinstance(command, list)
        assert all(isinstance(argument, str) for argument in command)
        assert "--force" not in command
        assert "-f" not in command
    for command in runner.calls:
        if command[:2] == ["git", "push"]:
            assert "main" not in command[2:]
    push = find_command(runner.calls, ("git", "push"))
    assert push[-1] == outcome.branch

    payload = json.loads(
        (
            settings.workspace_dir
            / "missions"
            / mission.id
            / "devops"
            / "devops-results.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["merged"] is False
    assert payload["publish"] is True


def test_devops_explicit_publish_requires_configuration_opt_in(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path, publish=False)
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir)

    outcome = DevOpsPromotion(settings, runner=runner).run(
        mission.id, publish=True
    )

    assert outcome.status == "planned"
    for command in runner.calls:
        assert tuple(command[:2]) not in {
            ("git", "fetch"),
            ("git", "switch"),
            ("git", "add"),
            ("git", "commit"),
            ("git", "push"),
            ("gh", "pr"),
        }
    assert not any(
        (settings.devops_repo_dir / "tests" / "generated").rglob("*")
    )


def test_devops_rejects_dangerous_git_configuration(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, publish=True)
    settings.devops_base_branch = "--force"
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(settings.devops_repo_dir)

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "blocked"
    assert "Configuration Git refusée" in (outcome.blocked_reason or "")
    assert runner.calls == []


def test_devops_redacts_sentinel_from_remote_failure(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, publish=True)
    settings.gemini_api_key = SENTINEL
    settings.devops_remote = SENTINEL
    mission = make_mission()
    write_sources(settings, mission.id)
    runner = FakeGitRunner(
        settings.devops_repo_dir,
        fetch_stderr=f"fatal: could not read from {SENTINEL}",
    )

    outcome = DevOpsPromotion(settings, runner=runner).run(mission.id)

    assert outcome.status == "blocked"
    assert SENTINEL not in (outcome.blocked_reason or "")
    assert SENTINEL not in outcome.summary
    for evidence in outcome.evidence_paths:
        assert SENTINEL not in Path(evidence).read_text(encoding="utf-8")


def test_devops_default_runner_sets_a_timeout(monkeypatch, tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.devops_timeout_seconds = 7.5
    captured: dict = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    DevOpsPromotion(settings)._default_runner(["git", "status"], tmp_path)

    assert captured["command"] == ["git", "status"]
    assert captured["timeout"] == 7.5
    assert "shell" not in captured
