"""Promotion Git des suites générées (agent 6, phase 7).

L'agent ne pousse jamais sur `main` : il crée toujours une branche dédiée
`qa/promotion-<mission>`, y commit les suites générées dans le workspace, puis
ouvre une pull request. La fusion reste une décision séparée.

Par défaut, l'agent fonctionne en **mode préparation** : il vérifie le dépôt et
calcule la promotion sans exécuter la moindre opération Git mutante. La
publication réelle exige `DEVOPS_PUBLISH_ENABLED=true` et une mission
explicitement approuvée (le planificateur classe les instructions Git/PR comme
sensibles).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, get_settings
from app.tools.workspace import write_mission_json, write_mission_text

PROMOTABLE_FILES = (
    ("api-automation/test_api_suite.py", "test_api_suite.py"),
    ("ui-automation/run_ui_checks.py", "run_ui_checks.py"),
)


@dataclass
class DevOpsOutcome:
    status: str
    branch: str | None = None
    commit: str | None = None
    pr_url: str | None = None
    promoted_files: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    summary: str = ""
    evidence_paths: list[str] = field(default_factory=list)
    commands: list[list[str]] = field(default_factory=list)


class DevOpsPromotion:
    """Prépare ou publie une branche et une PR pour les suites générées."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        runner: Callable[[list[str], Path], subprocess.CompletedProcess]
        | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._runner = runner or self._default_runner

    def _default_runner(
        self, command: list[str], cwd: Path
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.settings.devops_timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Point d'entrée
    # ------------------------------------------------------------------
    def run(
        self,
        mission_id: str,
        *,
        publish: bool | None = None,
    ) -> DevOpsOutcome:
        publish = (
            self.settings.devops_publish_enabled
            if publish is None
            else publish
        )
        commands: list[list[str]] = []
        repo_dir = Path(self.settings.devops_repo_dir).resolve()
        workspace = (
            Path(self.settings.workspace_dir) / "missions" / mission_id
        )
        sources = self._sources(workspace)
        destination_rel = Path("tests") / "generated" / mission_id
        branch = f"qa/promotion-{mission_id}"

        if not sources:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason=(
                    "Aucun test généré à promouvoir : la mission ne contient ni "
                    "suite pytest API ni script Playwright."
                ),
                commands=commands,
                publish=publish,
            )

        def git(*args: str) -> subprocess.CompletedProcess:
            command = ["git", *args]
            commands.append(command)
            return self._runner(command, repo_dir)

        try:
            top = git("rev-parse", "--show-toplevel")
        except OSError as exc:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason=(
                    f"Dépôt Git introuvable dans {repo_dir} "
                    f"({type(exc).__name__})."
                ),
                commands=commands,
                publish=publish,
            )
        if top.returncode != 0:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason="Le dossier de travail n'est pas un dépôt Git.",
                commands=commands,
                publish=publish,
            )
        repo_root = Path(top.stdout.strip() or repo_dir)
        promoted_files = [
            str(destination_rel / name) for _, name in sources
        ] + [str(destination_rel / "promotion.json")]

        # Mode préparation : aucune mutation Git, aucun fichier copié.
        if not publish:
            current = git("branch", "--show-current")
            clean = git("status", "--porcelain")
            clean_tree = clean.returncode == 0 and not clean.stdout.strip()
            detail = (
                "Mode préparation : aucune opération Git mutante n'a été "
                "exécutée (ni copie, ni commit, ni push, ni PR). "
                "Activez DEVOPS_PUBLISH_ENABLED=true pour publier."
            )
            summary = (
                f"Promotion préparée pour la mission {mission_id} : branche "
                f"`{branch}`, {len(promoted_files)} fichier(s) à promouvoir. "
                f"{detail}"
            )
            return self._finish(
                mission_id,
                status="planned",
                branch=branch,
                promoted_files=promoted_files,
                summary=summary,
                commands=commands,
                publish=publish,
                extra={
                    "current_branch": current.stdout.strip(),
                    "working_tree_clean": clean_tree,
                    "destination": str(destination_rel),
                },
            )

        # Mode publication : garde-fous avant toute mutation.
        dirty = git("status", "--porcelain")
        if dirty.returncode != 0 or dirty.stdout.strip():
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason=(
                    "Arbre de travail non propre : la promotion refuse de "
                    "mélanger des modifications locales non commitées. "
                    "Committer ou remiser ces modifications puis relancer."
                ),
                commands=commands,
                publish=publish,
            )

        exists = git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
        if exists.returncode == 0:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason=(
                    f"La branche locale `{branch}` existe déjà. "
                    "Aucune écriture n'a été effectuée."
                ),
                commands=commands,
                publish=publish,
            )

        fetch = git(
            "fetch",
            self.settings.devops_remote,
            self.settings.devops_base_branch,
        )
        if fetch.returncode != 0:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason=(
                    "Récupération de la branche de base impossible "
                    f"({_snippet(fetch.stderr)})."
                ),
                commands=commands,
                publish=publish,
            )

        switch = git(
            "switch",
            "-c",
            branch,
            f"{self.settings.devops_remote}/{self.settings.devops_base_branch}",
        )
        if switch.returncode != 0:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason=(
                    f"Création de la branche impossible ({_snippet(switch.stderr)})."
                ),
                commands=commands,
                publish=publish,
            )

        destination = repo_root / destination_rel
        shutil.rmtree(destination, ignore_errors=True)
        destination.mkdir(parents=True, exist_ok=True)
        for source, name in sources:
            shutil.copyfile(source, destination / name)
        manifest = {
            "mission_id": mission_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": f"workspace/missions/{mission_id}",
            "files": [name for _, name in sources],
            "note": (
                "Suites générées par les agents 4 et 5 (phase 6), promues par "
                "l'agent DevOps (phase 7)."
            ),
        }
        (destination / "promotion.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        added = git("add", "--", str(destination_rel))
        if added.returncode != 0:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason=(
                    f"Ajout Git impossible ({_snippet(added.stderr)})."
                ),
                commands=commands,
                publish=publish,
                extra={"destination": str(destination_rel)},
            )

        commit = git(
            "commit",
            "-m",
            f"test(qa): promote generated suites for mission {mission_id}",
        )
        if commit.returncode != 0:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                blocked_reason=(
                    f"Commit impossible ({_snippet(commit.stderr)})."
                ),
                commands=commands,
                publish=publish,
                extra={"destination": str(destination_rel)},
            )

        head = git("rev-parse", "HEAD")
        commit_id = head.stdout.strip() if head.returncode == 0 else None

        push = git(
            "push",
            "-u",
            self.settings.devops_remote,
            branch,
        )
        if push.returncode != 0:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                commit=commit_id,
                blocked_reason=(
                    "Push de la branche impossible "
                    f"({_snippet(push.stderr)}). La branche locale est conservée."
                ),
                commands=commands,
                publish=publish,
                extra={"destination": str(destination_rel)},
            )

        body = (
            f"Mission: {mission_id}\n\n"
            "Suites generees par les agents 4 et 5 (phase 6), promues par "
            "l'agent DevOps (phase 7).\n\n"
            "Fichiers:\n"
            + "\n".join(f"- {item}" for item in promoted_files)
            + "\n\nAucune modification applicative. La fusion reste une "
            "decision separee apres verification de la CI.\n"
        )
        pr_command = [
            "gh",
            "pr",
            "create",
            "--base",
            self.settings.devops_base_branch,
            "--head",
            branch,
            "--title",
            f"test(qa): promouvoir les suites generees de la mission {mission_id}",
            "--body",
            body,
        ]
        commands.append(pr_command)
        pr = self._runner(pr_command, repo_dir)
        if pr.returncode != 0:
            return self._finish(
                mission_id,
                status="blocked",
                branch=branch,
                commit=commit_id,
                blocked_reason=(
                    "Branche poussée mais pull request non créée "
                    f"({_snippet(pr.stderr)})."
                ),
                commands=commands,
                publish=publish,
                extra={"destination": str(destination_rel)},
            )

        pr_url = _last_non_empty_line(pr.stdout) or None
        summary = (
            f"Promotion publiée pour la mission {mission_id} : branche "
            f"`{branch}`, commit `{commit_id or 'inconnu'}`, pull request "
            f"{('`' + pr_url + '`') if pr_url else 'créée'}. "
            "Aucun push direct sur `main`, aucune fusion automatique."
        )
        return self._finish(
            mission_id,
            status="completed",
            branch=branch,
            commit=commit_id,
            pr_url=pr_url,
            promoted_files=promoted_files,
            summary=summary,
            commands=commands,
            publish=publish,
            extra={"destination": str(destination_rel)},
        )

    # ------------------------------------------------------------------
    # Preuves
    # ------------------------------------------------------------------
    @staticmethod
    def _sources(workspace: Path) -> list[tuple[Path, str]]:
        sources: list[tuple[Path, str]] = []
        for relative, name in PROMOTABLE_FILES:
            candidate = workspace / relative
            if candidate.is_file():
                sources.append((candidate, name))
        return sources

    def _finish(
        self,
        mission_id: str,
        *,
        status: str,
        branch: str | None,
        commit: str | None = None,
        pr_url: str | None = None,
        promoted_files: list[str] | None = None,
        blocked_reason: str | None = None,
        summary: str | None = None,
        commands: list[list[str]],
        publish: bool,
        extra: dict | None = None,
    ) -> DevOpsOutcome:
        promoted_files = promoted_files or []
        payload = {
            "mission_id": mission_id,
            "status": status,
            "publish": publish,
            "branch": branch,
            "commit": commit,
            "pr_url": pr_url,
            "promoted_files": promoted_files,
            "blocked_reason": blocked_reason,
            "merged": False,
            "commands": commands,
            **(extra or {}),
        }
        json_path = write_mission_json(
            self.settings,
            mission_id,
            "devops/devops-results.json",
            payload,
        )
        lines = [
            f"# Promotion Git — mission {mission_id}",
            "",
            f"- Statut : `{status}`",
            f"- Mode publication : `{publish}`",
            f"- Branche : `{branch or 'aucune'}`",
            f"- Commit : `{commit or 'aucun'}`",
            f"- Pull request : {pr_url or 'aucune'}",
            f"- Fusion automatique : `non`",
            "",
            "## Fichiers à promouvoir",
            "",
        ]
        if promoted_files:
            lines.extend(f"- `{item}`" for item in promoted_files)
        else:
            lines.append("Aucun fichier.")
        lines.extend(["", "## Commandes exécutées", ""])
        if commands:
            lines.extend(
                f"- `{' '.join(command)}`" for command in commands
            )
        else:
            lines.append("Aucune commande Git exécutée.")
        if blocked_reason:
            lines.extend(["", "## Non exécution", "", blocked_reason])
        lines.append("")
        md_path = write_mission_text(
            self.settings,
            mission_id,
            "devops/devops-report.md",
            "\n".join(lines),
        )

        if summary is None:
            summary = (
                f"Promotion Git non réalisée : {blocked_reason}"
                if blocked_reason
                else f"Promotion Git terminée pour la mission {mission_id}."
            )
        return DevOpsOutcome(
            status=status,
            branch=branch,
            commit=commit,
            pr_url=pr_url,
            promoted_files=promoted_files,
            blocked_reason=blocked_reason,
            summary=summary,
            evidence_paths=[str(json_path), str(md_path)],
            commands=commands,
        )


def _snippet(text: str, limit: int = 300) -> str:
    value = (text or "").strip().replace("\n", " ")
    return value[:limit] if value else "sans détail"


def _last_non_empty_line(text: str) -> str:
    for line in reversed((text or "").splitlines()):
        if line.strip():
            return line.strip()
    return ""
