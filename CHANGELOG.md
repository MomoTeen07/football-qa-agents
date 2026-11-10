# Changelog — Football QA Agents

Toutes les modifications notables du projet. L'objectif est de retrouver
rapidement **ce qui a changé, quand, et pourquoi**, sans relire tout l'historique
Git.

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Les versions sont propres au projet (aucune publication PyPI/npm).

## Règle de mise à jour

Toute modification (code, tests, configuration, outillage, documentation) doit :

1. mettre à jour **`README.md`** — usage, état visible, commandes ;
2. mettre à jour **`PROJECT_CONTEXT.md`** — point de reprise et décisions ;
3. ajouter une entrée dans **`CHANGELOG.md`** — section datée du jour.

Une PR n'est **pas** considérée terminée si l'un de ces trois fichiers est en
retard. En cas de doute, mettre à jour les trois.

> Le dépôt Git a été initialisé le **9 novembre 2026**. Les phases 1 à 5 sont
> regroupées dans le commit initial `2a3c929` ; leurs dates de développement
> antérieures ne sont pas tracées séparément.

---

## [Non publié]

### À venir

- **Phase 7** — agents 6 et 7 : agent DevOps (branche + PR) et reporting
  Allure/Markdown/JSON enrichi.
- **Phase 8** — bureau virtuel 2D : frontend séparé, SSE, personnages SVG.
- **Phase 9** — durcissement : sécurité, robustesse, documentation finale.

---

## [0.6.3] — 2026-11-10 — Phase 6 validée en réel et correctifs associés

### Ajouté

- **Exécution réelle complète de la phase 6** sur le PC personnel :
  stack `football-qa-test` opérationnelle, mission de référence
  `7e30889c18cd` avec **21/21 sondes API**, **27/27 tests pytest API**,
  **11/11 scénarios Playwright** et **0 anomalie**.

### Corrigé

- **Suite pytest générée invalide** (`app/tools/api_suite.py`) : les cas
  Postman étaient injectés via `json.dumps`, produisant `false`/`true`/`null`
  dans un fichier Python. Résultat : `NameError: name 'false' is not defined`
  et un unique faux échec de collecte au lieu des 27 tests. Les cas sont
  désormais injectés en littéraux Python (`pformat`).
- **Scénario Playwright de connexion** (`app/tools/ui_suite.py`) : le scénario
  enchaînait sur `/login` après la redirection `/favorites → /login`, dont
  `history.state.from` renvoie légitimement vers `/favorites`. Le scénario
  repasse maintenant par une page publique avant d'ouvrir `/login` et attend
  bien `/championships`.
- **Identifiant de l'environnement Postman** (`app/tools/openapi_postman.py`) :
  UUID aléatoire à chaque génération, donc diff parasite sur un fichier
  versionné. L'identifiant est maintenant déterministe (`uuid5`).

### Modifié

- Tests de non-régression : la suite API générée doit être du Python valide,
  le scénario UI doit repasser par une page publique, l'identifiant Postman
  doit être stable.
- Suite complète : **65 tests réussis** (64 avant).

### Environnement

- Projet cible `football-qa` présent à côté du projet QA ; stack de test
  `8002`/`5175`/`5434` construite et saine, comptes de test créés.
- `.env` local complété (Gemini et Telegram disponibles,
  `REAL_AGENTS_ENABLED=true`). Aucune valeur de secret n'est documentée.
- Chromium Playwright installé sur le PC personnel.

---

## [0.6.2] — 2026-11-09 — Nettoyage des branches fusionnées

### Modifié

- Suppression de `chore/reconstruct-local-env` (PR #1) et
  `docs/post-merge-status` (PR #2), en local et sur GitHub, après fusion.
- Seule la branche `main` subsiste ; tout nouveau travail part de `main`.
- `README.md` et `PROJECT_CONTEXT.md` alignés sur cet état.

### Pull request

- **PR #3** : <https://github.com/MomoTeen07/football-qa-agents/pull/3>
  (documentation uniquement).

---

## [0.6.1] — 2026-11-09 — Synchronisation documentaire post-merge

### Modifié

- **PR #1 marquée fusionnée** (merge commit `992d007`, 9 novembre 2026) :
  `main` devient la référence et contient la phase 6.
- `README.md` et `PROJECT_CONTEXT.md` : suppression du mode « avant merge »,
  reprise simplifiée en `git switch main` + `git pull`.
- `PROJECT_CONTEXT.md` : état Git et checklist de la phase 6 mis à jour.
- `CHANGELOG.md` : historique consolidé, ajout des commits `d958314` et
  `992d007` à la table de correspondance.

### Pull request

- **PR #2** : <https://github.com/MomoTeen07/football-qa-agents/pull/2>
  (documentation uniquement).

---

## [0.6.0] — 2026-11-09 — Phase 6 : automatisation API et UI

### Ajouté

- **Agent 4 `api_automation`** : génère une suite pytest depuis les GET sûrs de
  la collection Postman et les preuves de la phase 5, puis l'exécute.
  Rapport JUnit, journal expurgé, résultats JSON et rapport Markdown.
- **Agent 5 `ui_automation`** : génère et exécute des scénarios
  Playwright/Chromium sur le frontend de test, avec résultats JSON, rapport
  Markdown et captures d'écran en cas d'échec.
- **Reporter étendu** : lit `probe-results.json`,
  `api-automation-results.json` et `ui-automation-results.json`, et n'agrège
  que les anomalies réellement présentes.
- **Lanceur** `scripts/run_phase6_mission.py` : mission explicite API + UI.
- **Tests** : `tests/test_api_suite.py` (6), `tests/test_ui_suite.py` (9),
  `tests/test_phase6_agents.py` (8).
- **Documentation** : `reports/phase-6-agents-4-5.md`, section dédiée dans
  `README.md`, `CHANGELOG.md` et règle de mise à jour documentaire.
- **Dépendance** : `playwright==1.64.1` (navigateur Chromium installé
  séparément).
- **Outillage** : GitHub CLI `gh` 2.103.3 installé via winget et authentifié
  (jeton dans le keyring Windows, jamais dans le dépôt).

### Modifié

- Le reporter ne se limite plus aux sondes de la phase 5 : il consolide les
  preuves des phases 5 et 6.
- `PROJECT_CONTEXT.md` documente l'état réel, les deux PC et la procédure de
  reprise.

### Corrigé

- **Preuves périmées** : le rapport JUnit, les résultats UI et les captures
  d'une exécution précédente sont supprimés avant chaque nouveau run.
- **Faux positifs UI** : préflight du frontend **et** de l'API avant
  Playwright ; une stack arrêtée produit `blocked`, sans anomalie applicative.
- **Cibles interdites** : seules `localhost:8002` (API) et `localhost:5175`
  (UI) sont acceptées ; l'application réelle `8001`/`5174` est refusée.

### Validation

- Suite complète : **64 tests réussis** (`64 passed`).
- Mission de bout en bout hors ligne : tâches API et UI `blocked`, **0 anomalie
  inventée**, rapport cohérent.

### Limites

- L'exécution réelle API + UI reste à faire sur le PC professionnel (projet
  cible, stack `football-qa-test` et Chromium requis).
- Le reporting Allure complet relève de la phase 7.

### Pull request

- **PR #1** : <https://github.com/MomoTeen07/football-qa-agents/pull/1>
- Branche `chore/reconstruct-local-env` → `main`.
- **Fusionnée le 9 novembre 2026** par `MomoTeen07`
  (merge commit `992d007`).

---

## [0.5.0] — Phase 5 : agents 1 à 3 réels

### Ajouté

- Client Gemini free tier REST (`app/llm/gemini.py`), sans SDK payant.
- Modèle `gemini-3.5-flash` avec `thinkingConfig.thinkingBudget=0`
  (`gemini-2.5-flash` renvoyait HTTP 404 pour ce compte).
- Générateur Postman depuis l'OpenAPI réel : 11 requêtes, 5 dossiers
  (`health`, `auth`, `users`, `favorites`, `football`).
- Sondes API réelles (21 vérifications) limitées à `localhost:8002`, avec
  garde-fou sur `8001`.
- Preuves JSON/Markdown UTF-8 dans le workspace, secrets expurgés
  (`[redacted]`).
- Anomalies uniquement sur échec réel, avec reproduction et extrait de réponse.
- Agents 1 à 3 réels (`QAAnalystAgent`, `TestDesignerAgent`, `APITesterAgent`)
  avec repli déterministe.
- Reporter branché sur `probe-results.json`.
- Documentation : `reports/phase-5-agents-1-3.md`.

### Validation

- Suite complète : **41 tests réussis** à l'issue de la phase 5.
- Mission réelle `b745b4a199b7` : **21/21 sondes réussies, 0 anomalie**.

### Limites

- Test réel du bot Telegram en attente du token sur le PC personnel.

---

## [0.4.0] — Phase 4 : gateway Telegram

### Ajouté

- `python-telegram-bot==22.8` (dépendance et `.venv`).
- Allowlist stricte par `user_id` (`app/telegram/auth.py`).
- Gateway en **polling uniquement**, sans scheduler (`app/telegram/gateway.py`).
- Commandes `/start`, `/help`, `/status`, `/missions`, `/approve`, `/stop`.
- Missions exécutées dans `asyncio.to_thread` (Manager synchrone).
- Annulation (`/stop`) branchée dans le Manager et le graphe LangGraph.
- Tests d'allowlist et d'absence de mission automatique : **23 tests réussis**.
- Documentation : `reports/phase-4-telegram.md`.

### Limites

- Test réel du bot non exécuté sur le PC personnel (token absent).

---

## [0.3.0] — Phase 3 : socle du Manager

### Ajouté

- Stockage SQLite, EventBus, 7 agents de planification, CLI, approbation et
  rapports.
- Graphe LangGraph `plan → execute → review → report → finalize`.
- Tests du socle : **5 réussis**.
- Mission de démonstration `4e1c01636615` terminée.
- Documentation : `reports/phase-3-manager-core.md`.

---

## [0.2.0] — Phase 2 : isolation de la stack de test

### Ajouté

- Stack `football-qa-test` opérationnelle (`8002`, `5175`, `5434`).
- Comptes de test via `scripts/seed_test_data.py`.
- Base réelle laissée intacte.

### Validation

- Tests API rejoués sur `8002` : 2 réussis.
- Test Playwright « championships are visible » sur `5175` : 1 réussi.
- Documentation : `reports/phase-2-isolation.md`.

---

## [0.1.0] — Phase 1 : baseline

### Ajouté

- Relevé initial : `GET /health` → 200, UI → 200, Swagger → 200.
- 6 championnats retournés.
- Tests backend : 4 réussis ; tests de contrat API : 2 réussis.
- Playwright : 1 réussi, 1 échec de locator ambigu
  (`getByText('Football QA')` trouve 3 éléments) — problème de test, pas
  anomalie applicative.
- Documentation : `reports/baseline.md`.

---

## [0.0.0] — 2026-11-09 — Initialisation du dépôt

- Commit initial `2a3c929` : socle du projet et documentation des phases 1 à 5.
- `.env` et `.venv` exclus de Git.

---

## Correspondance des commits

| Commit | Date | Description |
|---|---|---|
| `2a3c929` | 2026-11-09 | Initial commit (phases 1 à 5) |
| `01d34a5` | 2026-11-09 | Documentation de l'environnement local reconstruit (Python 3.12, clés vides, 41 tests) |
| `9deffde` | 2026-11-09 | Documentation de la configuration deux PC (professionnel / personnel) |
| `9ee9de4` | 2026-11-09 | Phase 6 : automatisation API/UI et intégration reporter |
| `39dd4e9` | 2026-11-09 | Procédure de reprise et de synchronisation pour le PC professionnel |
| `0df3a6c` | 2026-11-09 | Point de reprise explicite en tête de `PROJECT_CONTEXT.md` |
| `9fd6db5` | 2026-11-09 | Documentation de la PR #1, de `gh` et de la reprise après merge |
| `d958314` | 2026-11-09 | Création de `CHANGELOG.md` et règle de mise à jour documentaire |
| `992d007` | 2026-11-09 | Merge de la PR #1 dans `main` (phase 6 fusionnée) |
| `2661c62` | 2026-11-09 | Synchronisation documentaire après le merge de la PR #1 |
| `e8a8dd0` | 2026-11-09 | Référence de la PR #2 dans le changelog |
| `8e33177` | 2026-11-09 | Merge de la PR #2 dans `main` |
