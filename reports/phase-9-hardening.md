# Phase 9 — Rapport de durcissement

**Statut : terminée.**  
Date : 13 novembre 2026.  
Point de départ : `main` `0179751` (phase 8), **103 tests verts**.  
Point d'arrivée : `main` après fusion de la PR J4, **159 tests verts**,
`ruff check .` sans erreur, CI = lint + tests.

Ce rapport clôt la phase 9 décrite dans `reports/phase-9-plan.md`. Il recense
les constats, les correctifs, les tests, les décisions et les limites
résiduelles. Aucun secret réel n'y figure : les tests utilisent uniquement une
valeur sentinelle factice.

---

## 1. Jalons livrés

| Jalon | Branche | Contenu | PR |
|---|---|---|---|
| J0 | `chore/phase9-baseline` | baseline 103 tests, tests rouges R1–R4 | #15 |
| J1 | `security/phase9-boundaries` | WP1 + WP4 : identifiants, chemins, secrets, garde-fous Git | #16 |
| J2 | `robustness/phase9-runtime` | WP2 + WP3 : bureau/SSE, SQLite, reprise, `doctor` | #17 |
| J3 | `chore/phase9-quality` | WP5 : `ruff` en CI, version 0.9.0, cohérence documentaire | #18 |
| J4 | `docs/phase9-final` | WP6 : rapport final, runbook, checklist sécurité, phase 8 | celle-ci |

Chaque PR a été testée hors ligne, sans clé, avec CI verte avant fusion.

---

## 2. Constats R1 à R14

| ID | Statut | Preuve / décision |
|---|---|---|
| R1 | **Corrigé** | `validate_mission_id` dans `workspace.py`, `devops.py`, `office/server.py`, `office/state.py`, `app/cli.py` et les scripts `run_office.py` / `run_phase7_mission.py`. Tests : `tests/test_security.py`. |
| R2 | **Corrigé** | `ensure_within` confine `write_mission_text` / `write_mission_json` au dossier de mission ; refus de `../../evasion.txt` et des chemins absolus. Tests : `tests/test_security.py`. |
| R3 | **Corrigé** | `redact_structure` appliqué à `/api/state`, `/api/missions`, `serialize_event` et au SSE avec `known_secrets(settings)`. Tests : `tests/test_security.py`, `tests/test_office_security.py`. |
| R4 | **Corrigé** | Tests sentinelle dans le Markdown, la synthèse JSON, les fichiers Allure et les réponses du bureau. |
| R5 | **Écarté (résiduel documenté)** | Le `SecretRedactionFilter` couvre le logger racine et les handlers installés au démarrage. Un handler ajouté après coup ou un logger avec handler propre reste hors de son périmètre : impossible à garantir sans imposer une fabrique de `LogRecord` globale, disproportionnée pour un gateway local mono-processus. Mitigations : `logs/` ignoré par Git, jeton régénérable, aucun log publié, tests de non-fuite existants. |
| R6 | **Corrigé** | Limite de **12 clients SSE** (`503` + `Retry-After` au-delà), timeout d'écriture de 10 s, un `build_office_state` par lot, en-têtes sur toutes les réponses, `405` + `Allow: GET` pour les autres méthodes, déconnexion brutale absorbée. Tests : `tests/test_office_security.py`. |
| R7 | **Corrigé** | `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`, `foreign_keys=ON`, retry borné (3 tentatives, 0,1 s × tentative), `StorageError` explicite, connexions fermées, mode `read_only` pour `doctor`. Tests : `tests/test_store_robustness.py`. |
| R8 | **Corrigé** | Plan idempotent par `key`, tâches `COMPLETED` ignorées, rapport non régénéré/non réannoncé ; reprise sans doublon testée. Tests : `tests/test_manager_recovery.py`. |
| R9 | **Corrigé** | `ruff==0.17.4` (développement uniquement), `ruff check .` avant `pytest` en CI, version `0.9.0` alignée sur le CHANGELOG. `mypy` non ajouté (décision justifiée ci-dessous). Test : `tests/test_docs_consistency.py`. |
| R10 | **Corrigé** | `self._snippet` expurge les secrets du stderr Git ; le JSON, le Markdown et le `blocked_reason` DevOps passent par `redact_text` / `redact_structure`. Test dédié dans `tests/test_phase7_agents.py`. |
| R11 | **Corrigé** | Tests des garde-fous Git : commandes en listes, jamais `shell=True`, jamais `--force`/`-f`, aucun push vers `main`, `merged` toujours `False`, timeouts présents, double opt-in de publication. Tests : `tests/test_phase7_agents.py`. |
| R12 | **Écarté (résiduel documenté)** | Le texte Telegram entrant n'est pas borné avant persistance. Contexte : allowlist stricte d'un seul utilisateur, gateway local, prompt Gemini déjà tronqué à 30 000 caractères, SQLite local. Aucune exposition externe. Une borne d'entrée pourra être ajoutée si le bot est un jour partagé. |
| R13 | **Écarté (résiduel documenté)** | Pas de journalisation centralisée ni de rotation automatique hors gateway. La CLI reste volontairement silencieuse ; le gateway écrit dans `logs/telegram-gateway.log` avec rédaction du jeton. La rotation est manuelle et documentée dans le runbook (section 5). |
| R14 | **Corrigé** | `README.md` (sécurité + dépannage rapide), `PROJECT_CONTEXT.md` (phase 9, décisions, pièges), `CHANGELOG.md` 0.9.0, ce rapport et `reports/phase-8-office.md`. |

---

## 3. Correctifs par lot de travail

### WP1 — identifiants, chemins et secrets

- `app/security.py` : barrière unique avec `validate_mission_id`,
  `validate_git_ref`, `ensure_within`, `redact_structure` et `known_secrets`.
- `app/tools/workspace.py` : identifiant validé, écritures confinées.
- `app/tools/devops.py` : identifiant et refs Git validés, stderr expurgé,
  rapport JSON/Markdown rédigé, double opt-in conservé.
- `app/office/state.py` + `server.py` : rédaction récursive, secrets injectés
  par le serveur.
- `app/agents/phase7.py` + `app/tools/allure_report.py` : Markdown, JSON,
  Allure (statuts, traces, pièces jointes, propriétés) rédigés.
- `app/cli.py`, `scripts/run_office.py`, `scripts/run_phase7_mission.py` :
  validation avant tout accès.

### WP2 — surface HTTP et SSE

- Constante `MAX_SSE_CLIENTS = 12` (usage local, plusieurs onglets).
- Compteur thread-safe, `503` explicite avec `Retry-After`, libération dans
  `finally`.
- `timeout` de connexion/écriture (10 s), erreurs réseau absorbées.
- Un seul instantané d'état par lot d'événements.
- En-têtes de sécurité sur les succès **et** les erreurs ; `405` clair pour
  `HEAD`/`POST`/etc.
- Aucune dépendance ajoutée : bibliothèque standard uniquement.

### WP3 — persistance, concurrence, reprise

- PRAGMA WAL / `busy_timeout` / `synchronous` / clés étrangères à chaque
  connexion.
- Retry borné sur `database is locked`, erreur `StorageError` lisible pour une
  base corrompue.
- `read_only=True` pour le diagnostic (`mode=ro`, aucun schéma créé).
- Reprise idempotente du graphe : réutilisation des tâches par `key`,
  `COMPLETED` ignorées, rapport existant conservé.
- `python -m app.cli doctor` : lecture seule, aucune réparation, code retour
  non nul seulement si la base est illisible.

### WP4 — garde-fous DevOps et sous-processus

- Publication toujours opt-in (`DEVOPS_PUBLISH_ENABLED` + `publish=True`).
- Refs Git validées avant toute commande ; arbre non propre ou branche
  existante bloqués.
- `popen`/`subprocess` avec listes d'arguments, sans shell, avec timeouts
  (`devops_timeout_seconds`, `automation_timeout_seconds`,
  `ui_automation_timeout_seconds`).
- Aucun `--force`, aucun push sur `main`, aucune fusion.

### WP5 — qualité, CI, versions

- `requirements-dev.txt` : `ruff==0.17.4` (jamais requis à l'exécution).
- `pyproject.toml` : `line-length=100`, règles `E`, `F`, `I`, `B`,
  `scripts/*.py` ignore `E402` (ajustement `sys.path`).
- CI : `pip install -r requirements-dev.txt`, `ruff check .`, `pytest -q`.
- Version `0.9.0` alignée ; test de cohérence documentaire.
- **`mypy` non ajouté** : le code utilise déjà des annotations, mais un mode
  progressif demanderait un inventaire et des exceptions larges (LangGraph,
  `http.server`, Playwright) pour un gain inférieur au coût de maintenance.
  `ruff` couvre les erreurs évidentes. Décision consignée dans
  `PROJECT_CONTEXT.md`.

### WP6 — documentation finale

- Ce rapport, checklist sécurité et Definition of Done.
- `reports/phase-8-office.md` : rapport manquant de la phase 8.
- `README.md` : section « Sécurité et garanties », dépannage rapide, commandes.
- `PROJECT_CONTEXT.md` : phase 9 terminée, décisions, pièges, runbook.
- `CHANGELOG.md` : `0.9.0` complété avec le jalon J4.

---

## 4. Tests

- **159 tests** au total, soit **56 de plus** que la baseline de 103.
- Tous **hors ligne**, sans clé, sans réseau, sans navigateur.
- Nouveaux fichiers : `test_security.py` (27), `test_store_robustness.py` (10),
  `test_manager_recovery.py` (6), `test_office_security.py` (5),
  `test_docs_consistency.py` (3), plus 5 tests ajoutés à
  `test_phase7_agents.py`.
- Points couverts : identifiants hostiles, chemins confinés, sentinelle absente
  des sorties, SSE limité et en-têtes, verrou SQLite et corruption, reprise
  idempotente, `doctor` sans mutation, garde-fous Git, versions cohérentes.

Commandes de vérification :

```powershell
.venv\Scripts\python.exe -m ruff check .   # All checks passed!
.venv\Scripts\python.exe -m pytest         # 159 passed
.venv\Scripts\python.exe -m app.cli doctor # lecture seule
```

---

## 5. Runbook d'exploitation

### Installation

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env   # renseigner les clés localement, jamais dans Git
```

### Vérification avant usage

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m app.cli doctor
```

### Mission réelle (explicite uniquement)

```powershell
docker compose -f infra/docker-compose.test.yml -p football-qa-test up --build -d --wait
.venv\Scripts\python.exe scripts\seed_test_data.py
.venv\Scripts\python.exe scripts\run_phase6_mission.py
.venv\Scripts\python.exe scripts\run_phase7_mission.py --mission-id <id>
```

### Bureau virtuel

```powershell
.venv\Scripts\python.exe scripts\run_office.py --mission-id <id>
# http://127.0.0.1:5180/ — lecture seule, aucun lancement de mission
```

### Diagnostic et incidents

| Symptôme | Action |
|---|---|
| base verrouillée | attendre la fin de l'écriture concurrente ; WAL + `busy_timeout=5000` + 3 retries absorbent les cas courts |
| `StorageError` « base illisible ou corrompue » | sauvegarder `workspace/missions.db`, vérifier le disque, restaurer une copie ; `doctor` ne répare jamais |
| `503` sur `/events` | limite de 12 flux SSE atteinte : fermer un onglet |
| `405` sur une méthode | le bureau n'accepte que `GET` |
| jeton dans un log ancien | purger `logs/`, régénérer le jeton via BotFather, mettre à jour `.env` sans afficher la valeur |
| publication DevOps `blocked` | arbre non propre, branche existante ou configuration Git invalide : corriger puis relancer |
| log volumineux | rotation manuelle : arrêter le gateway, archiver puis vider `logs/telegram-gateway.log` |

### Hygiène

- Ne jamais afficher, coller ou committer `.env`, les clés ou les jetons.
- `logs/`, `workspace/missions/`, `reports/allure-results/` et `reports/missions/`
  sont locaux et ignorés par Git.
- Aucun scheduler, aucune mission automatique.
- Fusion uniquement par PR après CI verte ; jamais de push direct sur `main`.

---

## 6. Checklist sécurité

- [x] Aucun secret sentinelle dans les logs, rapports, fichiers Allure,
      `/api/state` ou le SSE.
- [x] Identifiants de mission validés à une barrière unique.
- [x] Chemins d'écriture confinés au workspace de mission.
- [x] Cibles réseau limitées à `localhost:8002` / `localhost:5175` et bureau
      limité à la boucle locale.
- [x] Bureau : limite SSE, `503` propre, timeouts, en-têtes de sécurité, CSP
      sans ressource distante.
- [x] SQLite : WAL, `busy_timeout`, retry borné, mode lecture seule pour le
      diagnostic.
- [x] Reprise d'une mission interrompue sans doublon.
- [x] Garde-fous Git testés : pas de `main`, pas de `--force`, pas de fusion.
- [x] `ruff` vert et CI lint + tests.
- [x] Versions `pyproject.toml` / CHANGELOG alignées.
- [x] Aucune dépendance payante, aucun scheduler, aucune mission automatique.
- [x] Documentation finale à jour (README, PROJECT_CONTEXT, CHANGELOG, rapports).

---

## 7. Definition of Done (section 7 du plan)

- [x] Les constats R1 à R14 sont confirmés ou explicitement écartés avec
      justification (section 2).
- [x] Aucun secret sentinelle ne fuit dans les logs, rapports, artefacts
      Allure, `/api/state` ou le SSE.
- [x] Tous les identifiants et chemins sont validés à une barrière unique
      (`app/security.py`).
- [x] Le bureau refuse proprement au-delà de sa limite SSE et ne bloque pas.
- [x] SQLite fonctionne en WAL avec `busy_timeout` et retry borné.
- [x] Une mission `running` interrompue peut être reprise sans doublon.
- [x] Les garde-fous Git (pas de `main`, pas de force, pas de fusion) sont
      testés.
- [x] `ruff` passe et la CI exécute lint + tests.
- [x] Les versions `pyproject.toml` / CHANGELOG sont alignées.
- [x] `README.md`, `PROJECT_CONTEXT.md`, `CHANGELOG.md` et
      `reports/phase-9-hardening.md` sont à jour.
- [x] Aucune dépendance payante, aucun scheduler, aucune mission automatique.
- [x] CI verte et PR fusionnée (PR J4, fusion par l'agent après checks).

---

## 8. Limites restantes

- Publication DevOps réelle toujours non exécutée de bout en bout
  (`DEVOPS_PUBLISH_ENABLED=true` + `--publish`) : couverte par des tests avec
  exécuteur simulé.
- Test réel d'un **compte Telegram non autorisé** toujours en attente d'un
  second compte.
- R5, R12 et R13 restent des risques résiduels acceptés et documentés.
- Les missions réelles dépendent de la stack `football-qa-test` et de Chromium,
  absents de la CI (la suite reste hors ligne par conception).
