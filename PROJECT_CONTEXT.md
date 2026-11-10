# PROJECT_CONTEXT — Football QA Agents

Date du point de reprise : 10 novembre 2026  
Dernière action terminée : **CI GitHub Actions** et **reprise sur erreurs Gemini** (429/5xx). La phase 6 a été validée en réel sur le PC personnel : mission de référence `7e30889c18cd`, **21/21 sondes**, **27/27 tests pytest API**, **11/11 scénarios Playwright**, **0 anomalie**. Suite du système : **68 tests sur 68 réussis**.  
État global : **phases 1 à 6 terminées et validées en réel**. Le projet n'est pas terminé : les phases 7 à 9 restent à faire.

> **Point de reprise — lire ceci en premier**
>
> - `main` contient les phases 1 à 6 (PR #1, #2, #3 fusionnées).
>   La validation réelle et les correctifs arrivent par la **PR #4**
>   (`fix/phase6-real-run`, 10 novembre 2026).
> - Reprise : `git switch main` puis `git pull --ff-only origin main`.
> - Puis :
>   1. `.venv\Scripts\python.exe -m pip install -r requirements.txt`
>   2. `.venv\Scripts\python.exe -m pytest` → attendu **`68 passed`**
>   3. `.venv\Scripts\python.exe -m playwright install chromium`
>   4. démarrer la stack `football-qa-test`, puis `.venv\Scripts\python.exe scripts\run_phase6_mission.py`
> - Le projet cible `football-qa`, les clés et la stack de test sont
>   désormais disponibles sur le PC personnel : les missions réelles y sont
>   possibles.
> - Détail et précautions : section **« Reprise sur le PC professionnel »** ci-dessous.
> - **Documentation** : toute modification met à jour `README.md`,
>   `PROJECT_CONTEXT.md` et `CHANGELOG.md`.

---

## 1. Objectif du projet

Construire un système multi-agents QA local pour l’application `football-qa`, piloté par Telegram, avec :

- un Manager et 7 agents spécialisés ;
- des missions déclenchées uniquement à la demande ;
- des tests réels sur une stack isolée ;
- des rapports et des preuves locales ;
- un bureau virtuel 2D représentant les agents et les événements réels.

### Contraintes non négociables

- Aucun LLM payant : free tier uniquement.
- ChatGPT Go n’est pas utilisable via API.
- Utiliser **Postman**, pas Bruno.
- Aucune mission automatique, aucun cron, aucune surveillance QA permanente.
- L’application cible reste locale et non exposée sur Internet.
- Base de test séparée obligatoire ; ne jamais écrire dans la base réelle.
- Approbation humaine obligatoire pour :
  - tests intrusifs ;
  - actions destructrices ;
  - action sur l’application réelle ;
  - publication externe ;
  - validation finale d’une anomalie.
- Git : branche + PR uniquement, jamais de push direct sur `main`. Depuis le
  10 novembre 2026, **l'agent fusionne lui-même** la PR après vérification
  (plus d'attente de validation humaine).
- Documentation : toute modification met à jour `README.md`,
  `PROJECT_CONTEXT.md` et `CHANGELOG.md`.
- Tests de sécurité actifs non destructifs autorisés.
- Bureau virtuel simple en 2D avec personnages SVG et événements réels.
- Projet QA natif Windows dans un venv Python.
- Tests générés dans le workspace puis promus via PR.
- Budget logiciel : 0 €, aucune carte bancaire.

---

## 2. Environnements et ports

| Élément | Réel | Test isolé |
|---|---|---|
| Frontend | `http://localhost:5174` | `http://localhost:5175` |
| API | `http://localhost:8001` | `http://localhost:8002` |
| PostgreSQL | `localhost:5433` | `localhost:5434` |
| Base | `footballqa` | `footballqa_test` |
| Projet Compose | `football-qa` | `football-qa-test` |

- Le projet QA actuel est dans `C:\Users\MAbdo\Desktop\Football-Agent\football-qa-agents`.
- Le projet cible est présent sur cette machine :
  `C:\Users\MAbdo\Desktop\Football-Agent\football-qa` (copie de travail de
  `C:\Users\MAbdo\Desktop\Football-QA\MyFinalProject`). C’est le chemin
  attendu par `infra/docker-compose.test.yml` (`../../football-qa/...`).
- Le dossier `C:\Users\MAbdo\Desktop\Football-project\MyFinalProject` reste à
  ne pas utiliser.
- Docker Desktop est installé (`%LOCALAPPDATA%\Programs\DockerDesktop`) et le
  moteur tourne ; les 3 conteneurs `football-qa-test` (db, backend, frontend)
  sont **démarrés et sains**.
- La stack de test utilise `MOCK_FOOTBALL_API=true`.
- La base réelle est restée intacte : **5 utilisateurs / 2 favoris**.
- La base de test contient **2 utilisateurs / 0 favoris** (volume recréé le
  10 novembre 2026, comptes réensemencés via `scripts/seed_test_data.py`).
- Comptes de test : `qa.user1@example.com` et `qa.user2@example.com`.
- Le validateur d’email de l’application refuse les domaines `.test` ; utiliser `example.com`.

### Environnement Python local (vérifié le 10 novembre 2026)

- Python **3.12.10** installé en mode utilisateur via winget
  (`%LOCALAPPDATA%\Programs\Python\Python312\python.exe`).
- `.venv` recréé avec Python 3.12.10 ; dépendances `requirements.txt`
  installées.
- `.env` complété : **clés Gemini et Telegram disponibles**,
  `REAL_AGENTS_ENABLED=true`. Les valeurs ne sont jamais affichées.
- Suite de tests : `.venv\Scripts\python.exe -m pytest` → **68 passed**.
- `playwright==1.64.1` installé et **Chromium présent** dans
  `%LOCALAPPDATA%\ms-playwright` : l’exécution UI réelle fonctionne.
- Dépôt Git initialisé sur la branche `main` (commit initial `2a3c929`) ;
  `main` contient la phase 6 après le merge de la PR #1 (commit `992d007`).
  `.env` et `.venv` sont ignorés par Git.
- **GitHub CLI** `gh` 2.103.3 installé via winget et authentifié via le
  navigateur (jeton dans le keyring Windows). Aucun secret n'apparaît dans les
  fichiers du projet ni dans les rapports.

### Deux machines de travail

Le projet est utilisé sur deux PC. **Ne pas conclure à une régression ou à une
perte de projet quand un élément manque : vérifier d’abord sur quelle machine
on travaille.**

| Élément | PC professionnel | PC personnel |
|---|---|---|
| Utilisateur Windows | `stgadmin` | `MAbdo` |
| Projet QA | `C:\Users\stgadmin\Desktop\football-qa-agents` | `C:\Users\MAbdo\Desktop\Football-Agent\football-qa-agents` |
| Projet cible `football-qa` | présent (`C:\Users\stgadmin\Desktop\football-qa`) | présent (`...\Football-Agent\football-qa`) |
| Stack de test Docker | opérationnelle | opérationnelle |
| `.env` | clés Gemini + Telegram présentes | clés Gemini + Telegram présentes |
| Python | 3.12 avec `.venv` existant | 3.12.10, `.venv` prêt |
| Tests | 68 après `git pull` sur `main` | **68 passed** |

Conséquences :

- Les **deux PC** permettent désormais les missions réelles (sondes API, UI
  Playwright, Gemini). Seul le test réel du bot Telegram reste à faire.
- Les documents `reports/baseline.md` et les preuves historiques mentionnent
  des chemins `stgadmin` : ce sont des traces du PC professionnel, pas une
  configuration à reproduire sur le PC personnel.
- Sur le PC personnel, le projet cible est une **copie** de
  `MyFinalProject` : si une correction est faite côté application, la reporter
  aussi dans la copie (ou recopier le dossier) avant de relancer une mission.

### Reprise sur le PC professionnel

La phase 6 est sur `main` depuis la **PR #1** (merge commit `992d007`,
9 novembre 2026). Sa validation réelle et les correctifs associés arrivent par
la **PR #4** (`fix/phase6-real-run`, 10 novembre 2026).

```powershell
cd C:\Users\stgadmin\Desktop\football-qa-agents
git status                                  # vérifier l'absence de modifications locales
git switch main
git pull --ff-only origin main

.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest          # attendu : 68 passed
.venv\Scripts\python.exe -m playwright install chromium
```

Démarrer ensuite la stack de test, puis lancer
`scripts\run_phase6_mission.py`.

> Les branches `chore/reconstruct-local-env` (PR #1),
> `docs/post-merge-status` (PR #2) et `docs/branch-cleanup` (PR #3) ont été
> supprimées après leur fusion. Tout nouveau travail part de `main` et passe
> par une pull request.

Précautions :

- Si `git status` montre des modifications locales, les committer ou les
  remiser **avant** de changer de branche.
- `.env` et `.venv` ne sont pas synchronisés par Git : les clés restent locales
  à chaque PC et les dépendances sont à réinstaller.
- Ne pas pousser sur `main` : la fusion se fait par pull request, ouverte
  **et fusionnée** par l'agent après vérification des tests.
- **GitHub CLI** (`gh` 2.103.3) est installé sur le PC personnel pour créer les
  PR ; l'authentification est stockée dans le keyring Windows. Aucun secret
  n'est documenté ni journalisé.

---

## 3. État d'avancement

### Phases terminées

- [x] **Phase 1 — baseline**
  - `GET /health` → 200.
  - UI → 200.
  - Swagger → 200.
  - 6 championnats retournés.
  - Tests backend : 4 réussis.
  - Tests de contrat API : 2 réussis.
  - Playwright : 1 réussi, 1 échec de locator ambigu (`getByText('Football QA')` trouve 3 éléments).
  - L’échec Playwright est un problème de test, pas une anomalie applicative.
  - Rapport : `reports/baseline.md`.

- [x] **Phase 2 — isolation**
  - Stack `football-qa-test` opérationnelle.
  - Base réelle inchangée.
  - Comptes de test créés via `scripts/seed_test_data.py`.
  - Tests API rejoués sur `8002` : 2 réussis.
  - Test Playwright « championships are visible » sur `5175` : 1 réussi.
  - Rapport : `reports/phase-2-isolation.md`.

- [x] **Phase 3 — socle du Manager**
  - SQLite, EventBus, 7 agents de planification, CLI, approbation, rapports.
  - 5 tests réussis.
  - Mission de démonstration `4e1c01636615` terminée.
  - Rapport : `reports/missions/4e1c01636615.md`.
  - Documentation : `reports/phase-3-manager-core.md`.

### Phase 4 — Telegram : terminée côté code (test réel en attente du token)

Déjà fait :

- [x] `python-telegram-bot==22.8` installé dans `.venv`.
- [x] `python-telegram-bot==22.8` ajouté à `requirements.txt`.
- [x] Annulation (`/stop`) branchée dans `Manager` et dans le graphe LangGraph.
- [x] Tests relancés après ces modifications : **5 réussis**.
- [x] `.env` local créé avec `TELEGRAM_ALLOWED_USER_ID` renseigné.
- [x] Créer `app/telegram/__init__.py`.
- [x] Créer `app/telegram/auth.py` : allowlist stricte par `user_id`.
- [x] Créer `app/telegram/gateway.py` : polling uniquement, aucun scheduler.
- [x] Implémenter `/start`, `/help`, `/status`, `/missions`, `/approve`, `/stop`.
- [x] Créer et exécuter une mission sur texte libre.
- [x] Exécuter les missions dans `asyncio.to_thread` (le Manager est synchrone).
- [x] Ajouter des tests d’allowlist et d’absence de mission automatique : **23 tests réussis**.
- [x] Documenter la phase 4 dans `reports/phase-4-telegram.md`.
- [x] Mettre à jour `README.md` (phase 4).
- [ ] Test réel du bot : le token est désormais présent dans `.env` ; le test
      reste à exécuter (voir section 8, étape 3).

### Phase 5 — agents 1 à 3 : terminée côté code et validée réellement

Déjà fait :

- [x] Client Gemini free tier REST : `app/llm/gemini.py`, sans SDK payant.
- [x] Clé lue dans `.env`, jamais journalisée ni renvoyée dans une erreur.
- [x] Modèle `gemini-2.5-flash` remplacé par `gemini-3.5-flash` (HTTP 404
      « no longer available to new users » pour ce compte).
- [x] `thinkingConfig.thinkingBudget=0` activé pour Gemini 3.
- [x] Générateur Postman depuis l’OpenAPI réel : 11 requêtes, 5 dossiers.
- [x] Sondes API réelles limitées à `localhost:8002`, garde-fou sur `8001`.
- [x] Preuves JSON/Markdown UTF-8 dans le workspace, secrets expurgés.
- [x] Anomalies uniquement sur échec réel, avec reproduction et extrait.
- [x] Agents 1 à 3 réels avec repli déterministe ; agents 4 à 7 inchangés.
- [x] Reporter branché sur `probe-results.json`.
- [x] Suite complète à l’issue de la phase 5 : **41 tests réussis**.
- [x] Mission réelle `b745b4a199b7` : 21/21 sondes, 0 anomalie.
- [x] Documentation : `reports/phase-5-agents-1-3.md`.
- [x] mise à jour `README.md` (phase 5).
- [ ] Test réel du bot Telegram : token présent, test restant à exécuter.

### Phase 6 — agents 4 et 5 : terminée et validée en réel

Déjà fait :

- [x] Agent 4 `api_automation` : génération d’une suite pytest depuis la
      collection Postman et les preuves de la phase 5, exécution réelle,
      parsing JUnit, preuves JSON/Markdown et anomalies reproductibles.
- [x] Agent 5 `ui_automation` : génération et exécution de scénarios
      Playwright, résultats JSON, captures d’écran et anomalies reproductibles.
- [x] Garde-fous : cibles limitées à `localhost:8002` et `localhost:5175` ;
      l’application réelle `8001`/`5174` est refusée.
- [x] Préflight API **et** UI avant Playwright : une stack arrêtée produit
      `blocked`, sans fausse anomalie.
- [x] Suppression des preuves périmées (JUnit, résultats UI, captures) avant
      chaque exécution.
- [x] Reporter étendu : lit `probe-results.json`,
      `api-automation-results.json` et `ui-automation-results.json`, agrège les
      anomalies réellement présentes.
- [x] `scripts/run_phase6_mission.py` : lanceur explicite d’une mission
      phase 6.
- [x] `playwright==1.64.1` ajouté aux dépendances ; Chromium installé sur le
      PC personnel.
- [x] Tests hors ligne : `tests/test_api_suite.py`,
      `tests/test_ui_suite.py`, `tests/test_phase6_agents.py`.
- [x] Suite complète : **68 tests réussis**.
- [x] Documentation : `reports/phase-6-agents-4-5.md`.
- [x] Mise à jour `README.md` (phase 6).
- [x] **PR #1 fusionnée** dans `main` (merge `992d007`).
- [x] **Exécution réelle** le 10 novembre 2026 sur le PC personnel, stack de
      test saine, mission de référence `7e30889c18cd` :
      21/21 sondes, **27/27 tests pytest API**, **11/11 scénarios
      Playwright**, **0 anomalie**.
- [x] Correctifs issus de cette exécution (PR #4) :
      littéraux Python dans la suite générée (les `false` JSON provoquaient un
      `NameError`), scénario de connexion repassant par une page publique
      (`history.state.from` renvoyait vers `/favorites`), identifiant Postman
      déterministe (`uuid5`) pour éviter un diff à chaque mission.
- [ ] Test réel du bot Telegram : toujours à faire.

### Phases restantes

- [ ] **Phase 7 — agents 6 et 7** : DevOps (branche + PR) et reporting Allure/Markdown/JSON.
- [ ] **Phase 8 — bureau virtuel 2D** : frontend séparé, SSE, personnages SVG, événements réels.
- [ ] **Phase 9 — durcissement** : sécurité, robustesse, documentation finale.

---

## 4. Architecture actuelle et dernières modifications

### Vue d’ensemble

```text
Telegram (polling, allowlist)  ou  CLI
                │
                ▼
        Manager (app/orchestrator/manager.py)
                │
                ▼
   Graphe LangGraph : plan → execute → review → report → finalize
                │
   ┌────────────┼─────────────┬──────────────┬─────────────┐
   ▼            ▼             ▼              ▼             ▼
QA Analyst  Test Designer  API Tester   API Auto +    QA Reporter
(Gemini)    (Gemini)       (OpenAPI +   UI Auto       (preuves réelles
                           Postman +    (pytest +     phases 5 et 6)
                           sondes HTTP)  Playwright)
```

- Le **Manager** crée la mission, planifie les tâches, applique
  l’approbation/l’annulation et publie les événements.
- Le **graphe LangGraph** exécute les tâches dans l’ordre des dépendances et
  transmet au reporter les résultats et preuves de chaque tâche.
- Les **agents 1 à 3** sont réels depuis la phase 5.
- Les **agents 4 et 5** (API Automation, UI Automation) sont réels depuis la
  phase 6 et validés **en réel** le 10 novembre 2026.
- L’**agent 6 (DevOps)** reste un stub ; l’**agent 7 (reporter)** est réel et
  agrège désormais les preuves des phases 5 et 6. Le reporting Allure complet
  relève de la phase 7.
- L’**EventBus** et le **store SQLite** journalisent missions, tâches et
  événements localement.

### Phase 5 — agents 1 à 3

- `app/llm/gemini.py`
  - Client REST Gemini free tier, sans SDK payant.
  - Clé lue dans `.env`, jamais journalisée ni renvoyée dans une erreur.
  - `thinkingBudget=0` pour les modèles Gemini 3.
  - Repli déterministe : une erreur LLM ne bloque pas la mission et n’invente
    aucun résultat.

- `app/tools/openapi_postman.py`
  - Analyse l’OpenAPI réel de la stack de test.
  - Génère `postman/collections/football-qa.json` (11 requêtes, dossiers
    `health`, `auth`, `users`, `favorites`, `football`).
  - Génère `postman/environments/football-qa-test.json`.
  - Ajoute les en-têtes Bearer, les corps d’exemple et les scripts de test
    Postman.

- `app/tools/api_probe.py`
  - Exécute 21 vérifications HTTP réelles.
  - Refuse toute cible autre que `localhost`/`127.0.0.1` sur le port `8002`.
  - Écrit `probe-results.json`, `probe-report.md`, `openapi.json` et
    `openapi-analysis.json` dans le workspace de mission.
  - Expurge mots de passe, jetons et en-têtes d’autorisation (`[redacted]`).
  - Ne déclare une anomalie qu’en cas d’échec réel, avec méthode, chemin,
    attendu, obtenu, reproduction et extrait de réponse.
  - Nettoie uniquement les favoris de sonde résiduels (`team_id=999001`).

- `app/agents/phase5.py`
  - `QAAnalystAgent`, `TestDesignerAgent`, `APITesterAgent`.
  - Chaque agent conserve un repli déterministe si `REAL_AGENTS_ENABLED=false`,
    si la clé est absente ou si Gemini échoue.

- `app/agents/stubs.py`
  - À l’issue de la phase 5, le `QAReporterAgent` lit `probe-results.json` et
    n’énonce que des anomalies réellement présentes.
  - Les agents 4 à 7 étaient encore inchangés à ce stade ; voir la phase 6
    ci-dessous pour l’état actuel.

- `app/orchestrator/manager.py`
  - Injecte `GeminiClient` et `ApiProbe` dans les agents réels.

- `app/orchestrator/graph.py`
  - Le contexte du reporter transporte désormais `result` et `evidence`.

### Phase 6 — agents 4 et 5

- `app/agents/phase6.py`
  - `APIAutomationAgent` et `UIAutomationAgent`, avec repli déterministe si
    `REAL_AGENTS_ENABLED=false`.
  - Une cible interdite ou indisponible produit un statut bloqué, sans
    anomalie applicative.

- `app/tools/api_suite.py`
  - Génère `api-automation/test_api_suite.py` depuis la collection Postman
    (uniquement les GET sûrs) et les preuves de la phase 5.
  - Préflight `GET /health` sur `localhost:8002`.
  - Exécution pytest, parsing JUnit, journal expurgé, résultats JSON et rapport
    Markdown.
  - Suppression du JUnit périmé avant chaque exécution.
  - Anomalie uniquement pour un test réellement en échec, avec reproduction et
    preuve.
  - Les cas Postman sont injectés en **littéraux Python** (`pformat`) : un
    `json.dumps` produisait `false`/`true` et rendait la suite non collectable.

- `app/tools/ui_suite.py`
  - Génère `ui-automation/run_ui_checks.py` (Playwright/Chromium).
  - Préflight du frontend **et** de l’API avant lancement.
  - Résultats JSON, rapport Markdown, captures d’écran en cas d’échec.
  - Suppression des résultats et captures périmés avant chaque exécution.
  - Cibles limitées à `localhost:5175` et `localhost:8002`.
  - Le scénario de connexion repasse par une page publique avant `/login` :
    un reload conserve `history.state.from`, qui renvoie vers `/favorites`.

- `app/agents/stubs.py`
  - Le reporter lit désormais `probe-results.json`,
    `api-automation-results.json` et `ui-automation-results.json`.
  - Il agrège les anomalies réellement présentes et conserve les phrases de
    repli quand aucune exécution n’a eu lieu.

- `scripts/run_phase6_mission.py`
  - Lanceur explicite d’une mission API + UI sur la stack de test.

- `requirements.txt`
  - `playwright==1.64.1` (le navigateur Chromium s’installe séparément avec
    `python -m playwright install chromium`).

### Gateway Telegram (phase 4, inchangé)

- Polling uniquement, aucun scheduler, aucun `JobQueue`.
- Allowlist stricte sur chaque update (groupe `-1`).
- Commandes `/start`, `/help`, `/status`, `/missions`, `/approve`, `/stop`.
- Texte libre : création puis exécution d’une mission.
- Missions exécutées via `asyncio.to_thread` (Manager synchrone).
- Un seul `Manager` par processus, protégé par un verrou thread-safe.

### Vérification

```powershell
.venv\Scripts\python.exe -m pytest
# 68 passed
```

CI : `.github/workflows/tests.yml` rejoue la même suite sur chaque PR et sur
chaque push vers `main` (Python 3.12, sans clé). C'est le garde-fou avant
fusion automatique par l'agent.

Mission réelle de référence (10 novembre 2026) :

```powershell
.venv\Scripts\python.exe scripts\seed_test_data.py
.venv\Scripts\python.exe scripts\run_phase6_mission.py
# MISSION_ID=7e30889c18cd
# PROBE 21/21, API_TESTS=27 API_PASSED=27, UI_CHECKS=11 UI_PASSED=11
# API_ANOMALIES=0, UI_ANOMALIES=0
```

---

## 5. Fichiers créés ou modifiés

### Projet `football-qa-agents`

| Fichier | Rôle |
|---|---|
| `README.md` | Présentation, structure, stack, avancement |
| `.gitignore` | Exclusion des secrets, venv, artefacts, bases locales |
| `.env.example` | Modèle de configuration sans secrets |
| `.env.test.example` | Modèle de configuration de test |
| `.env` | Configuration locale réelle, **ignorée par Git** |
| `requirements.txt` | Dépendances Python, Telegram et Playwright inclus |
| `pyproject.toml` | Configuration pytest |
| `.github/workflows/tests.yml` | CI GitHub Actions : pytest sur chaque PR et sur `main` |
| `PROJECT_CONTEXT.md` | Ce point de reprise |
| `CHANGELOG.md` | Historique daté des modifications et règle de mise à jour |
| `app/__init__.py` | Package principal |
| `app/config.py` | Settings Pydantic, chemins, secrets |
| `app/domain/models.py` | Mission, Task, Event, AgentResult, statuts |
| `app/store/sqlite_store.py` | Stockage SQLite missions/tâches/événements |
| `app/events/bus.py` | EventBus réel avec abonnés |
| `app/agents/base.py` | Interface `BaseAgent` |
| `app/agents/phase5.py` | Agents 1 à 3 réels (Gemini, OpenAPI, Postman, sondes) |
| `app/agents/stubs.py` | Agent DevOps (stub) et reporter étendu phases 5/6 |
| `app/llm/__init__.py` | Package d’intégration LLM |
| `app/llm/gemini.py` | Client Gemini free tier REST, sans fuite de clé |
| `app/tools/__init__.py` | Package des outils réels |
| `app/tools/workspace.py` | Écriture UTF-8 des preuves de mission |
| `app/tools/redaction.py` | Expurgation des secrets dans les preuves |
| `app/tools/openapi_postman.py` | Analyse OpenAPI et génération Postman (IDs stables) |
| `app/tools/api_probe.py` | Sondes API réelles, garde-fou 8002, preuves, anomalies |
| `app/tools/api_suite.py` | Suite pytest API générée, exécution, JUnit, preuves |
| `app/tools/ui_suite.py` | Scénarios Playwright générés, exécution, captures, preuves |
| `app/agents/phase6.py` | Agents 4 et 5 (API Automation, UI Automation) |
| `app/orchestrator/planner.py` | Planification déterministe et détection d’approbation |
| `app/orchestrator/state.py` | `MissionState` LangGraph |
| `app/orchestrator/graph.py` | Graphe plan → execute → review → report → finalize |
| `app/orchestrator/manager.py` | Manager, cycle de mission, approbation, annulation, agents réels |
| `app/cli.py` | CLI `create`, `run`, `approve`, `status`, `events`, `list`, `demo` |
| `app/telegram/__init__.py` | Package Telegram |
| `app/telegram/auth.py` | Allowlist stricte par `user_id` |
| `app/telegram/gateway.py` | Gateway Telegram en polling, sans scheduler |
| `tests/test_manager.py` | 5 tests du socle |
| `tests/test_telegram_auth.py` | 5 tests de l’allowlist |
| `tests/test_telegram_gateway.py` | 13 tests du gateway et des garde-fous |
| `tests/test_gemini_client.py` | 8 tests du client Gemini (dont reprise 429/5xx et absence de fuite de clé) |
| `tests/test_openapi_postman.py` | 3 tests OpenAPI et Postman |
| `tests/test_api_probe.py` | 4 tests des sondes, du garde-fou et des anomalies |
| `tests/test_phase5_agents.py` | 6 tests des agents phase 5 et du reporter |
| `tests/test_api_suite.py` | 6 tests de la suite pytest API générée |
| `tests/test_ui_suite.py` | 9 tests de la suite Playwright et des garde-fous |
| `tests/test_phase6_agents.py` | 9 tests des agents 4/5 et du reporter |
| `infra/docker-compose.test.yml` | Stack de test isolée |
| `scripts/seed_test_data.py` | Création des comptes de test |
| `scripts/run_phase5_mission.py` | Lanceur explicite d’une mission phase 5 |
| `scripts/run_phase6_mission.py` | Lanceur explicite d’une mission phase 6 API + UI |
| `postman/collections/football-qa.json` | Collection Postman réelle (11 requêtes) |
| `postman/environments/football-qa-test.json` | Environnement Postman de test |
| `reports/baseline.md` | Baseline |
| `reports/phase-2-isolation.md` | Validation isolation |
| `reports/phase-3-manager-core.md` | Validation socle Manager |
| `reports/phase-4-telegram.md` | Validation connexion Telegram |
| `reports/phase-5-agents-1-3.md` | Validation phase 5 |
| `reports/phase-6-agents-4-5.md` | Validation phase 6 (hors ligne + réel) |
| `reports/missions/4e1c01636615.md` | Rapport de mission de démonstration (local, ignoré par Git) |
| `reports/missions/b745b4a199b7.md` | Rapport de la mission phase 5 de référence (local) |
| `reports/missions/7e30889c18cd.md` | Rapport de la mission phase 6 validée en réel (local) |
| `workspace/missions/b745b4a199b7/` | Preuves de la mission phase 5 (locales) |
| `workspace/missions/7e30889c18cd/` | Preuves de la mission phase 6 réelle (locales) |
| `workspace/missions.db` | Base SQLite locale des missions |
| `workspace/missions/.gitkeep` | Maintien du dossier |
| `reports/missions/.gitkeep` | Maintien du dossier |

### Application cible `football-qa`

Aucun fichier métier n’a été modifié.  
Les artefacts Playwright générés pendant le baseline ont été supprimés.  
Le dépôt `football-qa` est resté propre.

---

## 6. Décisions techniques prises

- **Orchestration** : LangGraph 1.2.20 + logique déterministe.
- **LLM** : Gemini free tier principal (`gemini-3.5-flash`), Groq/Mistral en secours.
- **Gemini** : API REST directe, sans SDK payant ; `thinkingBudget=0` pour Gemini 3 ; erreurs réduites au code HTTP ; clé jamais journalisée.
- **Modèle Gemini** : `gemini-2.5-flash` et `gemini-2.5-flash-lite` renvoient HTTP 404 « no longer available to new users » pour ce compte ; `gemini-3.5-flash` est le modèle validé.
- **Telegram** : `python-telegram-bot` 22.8, polling, allowlist stricte.
- **Veilleur Telegram** : minimal, toujours actif ; Manager/agents démarrés uniquement sur message autorisé.
- **Aucun scheduler** : pas de `JobQueue`, pas de cron, pas de mission automatique.
- **Exécution** : missions lancées via `asyncio.to_thread` car le Manager est synchrone.
- **Stockage** : SQLite local pour le pilotage QA, indépendant de PostgreSQL.
- **Base de test** : PostgreSQL `5434`, backend `8002`, frontend `5175`.
- **Mode football** : `MOCK_FOOTBALL_API=true` pour des tests déterministes.
- **Rapports** : Markdown/JSON puis Allure, en français.
- **Bureau virtuel** : frontend séparé, SSE, personnages SVG.
- **Jira/Xray/Squash** : non retenus.
- **Git** : branche + PR uniquement, jamais de push direct sur `main`. Fusion réalisée par l'agent (décision du 10 novembre 2026, remplace la validation humaine).
- **CI** : GitHub Actions, `pytest` sur chaque PR et sur `main` (Python 3.12, sans clé). Garde-fou qui remplace la relecture humaine avant fusion.
- **Gemini** : les `429` et `5xx` sont retentés (3 tentatives, backoff 1 s puis 2 s, plafond 8 s) ; erreurs réseau et `4xx` définitifs immédiats ; repli déterministe après échec.
- **Agents actuels** : agents 1 à 3 réels (phase 5), agents 4 et 5 réels et validés en réel (phase 6), agent 6 (DevOps) encore stub, agent 7 (reporter) réel mais sans Allure. Aucune anomalie inventée.
- **Automatisation API** : suite pytest générée depuis les GET sûrs de la collection Postman ; JUnit + JSON + Markdown ; cible limitée à `localhost:8002` ; cas injectés en littéraux Python, jamais en JSON.
- **Automatisation UI** : Playwright/Chromium, cible limitée à `localhost:5175` et API `localhost:8002` ; préflight UI + API ; captures en cas d’échec ; connexion testée depuis une page publique (pas après une redirection protégée).
- **Postman (identifiants)** : UUID déterministe (`uuid5`) pour la collection et l’environnement, afin que la régénération ne produise pas de diff parasite.
- **Playwright** : `playwright==1.64.1` ; le navigateur s’installe séparément (`python -m playwright install chromium`).
- **Sondes API** : cible strictement limitée à `localhost`/`127.0.0.1:8002` ; l’application réelle `8001` est refusée.
- **Anomalies** : uniquement sur échec réel, avec reproduction et extrait de preuve.
- **Postman** : collection générée depuis l’OpenAPI réel, pas de collection écrite à la main.
- **Email de test** : `example.com` car `.test` est refusé par le validateur.

---

## 7. Configuration, secrets et restes à faire

`.env` est présent et ignoré par Git. Il a été **complété le 10 novembre 2026**
avec les clés Gemini et Telegram. Aucune valeur de secret n’est reproduite
dans ce document.

État vérifié au moment du point de reprise :

| Variable | État |
|---|---|
| `TELEGRAM_ALLOWED_USER_ID` | renseigné dans `.env` (identifiant non reproduit ici) |
| `TELEGRAM_BOT_TOKEN` | **renseigné** → test réel du bot possible |
| `GEMINI_API_KEY` | **renseignée** → agents 1 à 3 réellement enrichis |
| `LLM_MODEL` | `gemini-3.5-flash` |
| `REAL_AGENTS_ENABLED` | `true` |
| `TEST_API_URL` | `http://localhost:8002` |
| `TEST_UI_URL` | `http://localhost:5175` |
| `TEST_USER1_EMAIL` / `TEST_USER2_EMAIL` | comptes de test locaux |
| `GROQ_API_KEY` / `MISTRAL_API_KEY` | non utilisés |

Sans clé, le système reste utilisable : les 68 tests passent et les agents
réels basculent sur leur repli déterministe.

Historique utile :

- Les deux clés avaient d’abord été déposées dans
  `C:\Users\stgadmin\Desktop\football-qa\.env` (application cible), puis
  copiées dans `football-qa-agents\.env` sans affichage.
- Elles ont été récupérées sur le PC personnel le 10 novembre 2026 et placées
  dans `football-qa-agents\.env` (seul fichier lu par `app/config.py`).
- Ne jamais afficher, journaliser ou coller ces valeurs dans le chat, un
  rapport ou une preuve.

### Configuration Telegram restant à effectuer

- `TELEGRAM_BOT_TOKEN` est renseigné ; le bot n’a pas encore été testé en réel.
- Pour le tester : lancer `.venv\Scripts\python.exe -m app.telegram.gateway`
  puis envoyer `/start`, un texte libre, `/status`, `/approve`, `/stop`.
- Vérifier que le token n’a jamais été publié ; en cas de doute, le régénérer
  via BotFather et mettre à jour `.env` sans afficher la nouvelle valeur.

### Configuration Gemini

- `GEMINI_API_KEY` est renseignée et `REAL_AGENTS_ENABLED=true` : les agents 1
  à 3 sont réellement enrichis (constaté sur les missions du 10 novembre 2026).
- Le free tier peut renvoyer une erreur passagère (429/quota) : le repli
  déterministe s’applique alors sans bloquer la mission. Ne pas interpréter ce
  repli comme une anomalie applicative.
- Ne pas revenir à `gemini-2.5-flash` ni `gemini-2.5-flash-lite` : HTTP 404
  pour ce compte.
- Ne jamais exposer la clé dans une URL de rapport, un log ou une preuve.

---

## 8. Comment reprendre dans une nouvelle conversation

### Étape 0 — vérifier l’environnement et la machine

Identifier d’abord la machine : `stgadmin` = PC professionnel (projet cible et
clés disponibles) ; `MAbdo` = PC personnel (projet cible, clés, Chromium et
stack de test également disponibles depuis le 10 novembre 2026).

```powershell
cd C:\Users\MAbdo\Desktop\Football-Agent\football-qa-agents

# Tests du système QA
.venv\Scripts\python.exe -m pytest

# Stack de test (nécessite le projet cible football-qa)
docker compose -f infra/docker-compose.test.yml -p football-qa-test ps
```

Si `.venv` est absent (nouvelle machine) :

```powershell
# Python 3.12 requis (pyproject.toml : requires-python >= 3.12)
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Uniquement pour l'exécution UI réelle (pas nécessaire pour pytest)
.venv\Scripts\python.exe -m playwright install chromium
```

Si `.env` est absent : le recréer depuis `.env.example`
(`Copy-Item .env.example .env`). Les clés peuvent rester vides.

Si la stack n’est pas démarrée :

```powershell
docker compose -f infra/docker-compose.test.yml -p football-qa-test up --build -d --wait
```

> **Prérequis** : le projet cible doit être présent dans un dossier
> `football-qa` voisin (le compose référence `../../football-qa/backend` et
> `../../football-qa/frontend`). Sur cette machine, il est présent en
> `C:\Users\MAbdo\Desktop\Football-Agent\football-qa`.

Vérifier :

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8002/health
Invoke-WebRequest -UseBasicParsing http://localhost:5175/
```

Attendu : `68 passed` et stack `healthy` sur `8002`, `5434` et `5175`.
Ne jamais sonder `8001` avec les outils du projet.

### Étape 1 — vérifier l’état livré

```powershell
# Comptes de test (base de test recréée)
.venv\Scripts\python.exe scripts\seed_test_data.py

# Preuves de la mission de référence phase 6 (locales, ignorées par Git)
Get-ChildItem workspace\missions\7e30889c18cd -Recurse

# Collection Postman
Get-Content postman\collections\football-qa.json -TotalCount 20
```

Attendu : 21/21 sondes, 27/27 tests API, 11/11 scénarios UI, 0 anomalie,
11 requêtes Postman. Les rapports de mission sont **locaux** et absents d’un
clone frais : c’est normal.

### Étape 2 — relancer une mission phase 5 (optionnel)

```powershell
.venv\Scripts\python.exe scripts\run_phase5_mission.py
```

Le script refuse de s’exécuter si `REAL_AGENTS_ENABLED=false`. Il crée une
mission explicite, exécute les agents 1 à 3, écrit les preuves et affiche
`PROBE_CHECKS`, `PROBE_PASSED`, `PROBE_ANOMALIES`.

### Étape 2 bis — relancer une mission phase 6 API + UI (optionnel)

```powershell
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe scripts\run_phase6_mission.py
```

Le script refuse de s’exécuter si `REAL_AGENTS_ENABLED=false`. Il génère et
exécute la suite pytest API puis les scénarios Playwright, écrit les preuves et
affiche `API_STATUS`, `API_TESTS`, `API_PASSED`, `API_FAILED`,
`API_ANOMALIES` et l’équivalent UI.

> Résultat attendu sur une stack saine : `API_TESTS=27`, `API_PASSED=27`,
> `UI_CHECKS=11`, `UI_PASSED=11`, anomalies à `0`. Un statut `blocked` signifie
> que la stack est arrêtée, pas qu’une anomalie a été trouvée.

### Étape 3 — tester réellement le bot Telegram (optionnel)

```powershell
.venv\Scripts\python.exe -m app.telegram.gateway
```

Puis, depuis le compte autorisé : `/start`, un texte libre, `/status <id>`,
`/approve <id>` si demandé, `/stop <id>`. Aucun scheduler ne doit démarrer.

> Le token est désormais présent dans `.env` ; seul le test manuel reste à
> faire.

### Étape 4 — prochaine phase de développement

**Phase 7 — agents 6 et 7** : agent DevOps (branche + PR, sans push direct sur
`main`) et reporting Allure/Markdown/JSON enrichi. Les phases 1 à 6 sont
terminées et validées en réel. Ne pas démarrer la phase 7 sans demande
explicite.

### En cas de problème connu

| Symptôme | Cause probable | Action |
|---|---|---|
| `Gemini a répondu HTTP 404` | modèle obsolète | garder `LLM_MODEL=gemini-3.5-flash` |
| `Conception Gemini indisponible (GeminiError)` | quota/429 du free tier | repli déterministe normal ; relancer plus tard, aucune anomalie applicative |
| `GEMINI_API_KEY absente` | clé dans le mauvais `.env` | vérifier `football-qa-agents\.env`, ne pas afficher la valeur |
| `UnsafeTargetError` | cible autre que `localhost:8002` | corriger `TEST_API_URL`, ne pas viser `8001` |
| `UnsafeUiTargetError` | cible UI autre que `localhost:5175` | corriger `TEST_UI_URL` |
| `Playwright n'a produit aucun résultat` | navigateur Chromium absent | `python -m playwright install chromium` |
| `API_STATUS=blocked` en phase 6 | API de test arrêtée | démarrer la stack `football-qa-test` |
| tests lents ou appels réels | `REAL_AGENTS_ENABLED=true` dans l’environnement | les tests forcent déjà `false` ; vérifier les overrides |
| accents illisibles en console | rendu PowerShell | les fichiers sont UTF-8 ; lire avec Python si besoin |

---

## 9. Commandes utiles

```powershell
# Tests du système QA
.venv\Scripts\python.exe -m pytest

# Mission réelle phase 5 (explicite, sur la stack de test)
.venv\Scripts\python.exe scripts\run_phase5_mission.py

# Navigateur requis pour l'exécution UI réelle
.venv\Scripts\python.exe -m playwright install chromium

# Mission réelle phase 6 API + UI (explicite, sur la stack de test)
.venv\Scripts\python.exe scripts\run_phase6_mission.py

# Gateway Telegram (polling, allowlist)
.venv\Scripts\python.exe -m app.telegram.gateway

# Créer une mission
.venv\Scripts\python.exe -m app.cli create "Analyse l'application et propose un plan de test."

# Exécuter une mission
.venv\Scripts\python.exe -m app.cli run <mission_id>

# Approuver et exécuter
.venv\Scripts\python.exe -m app.cli approve <mission_id>

# Statut
.venv\Scripts\python.exe -m app.cli status <mission_id>

# Événements
.venv\Scripts\python.exe -m app.cli events <mission_id>

# Liste des missions
.venv\Scripts\python.exe -m app.cli list

# Mission de démonstration
.venv\Scripts\python.exe -m app.cli demo
```

---

## 10. Avertissements importants

- La console PowerShell peut mal afficher l’UTF-8 ; les fichiers sont bien en UTF-8.
- Utiliser Python pour vérifier le contenu des rapports si nécessaire.
- Ne pas écrire dans la base réelle `footballqa`.
- Ne pas lancer de mission automatique.
- Ne pas ajouter de scheduler.
- Ne pas publier d’anomalie sans preuve.
- Ne pas pousser directement sur `main`.
- Ne pas afficher, journaliser ou envoyer les secrets Telegram/Gemini.
- Les sondes refusent toute cible autre que `localhost:8002`.
- Le projet `football-qa-agents` est initialisé en Git sur `main` (commit initial `2a3c929`).
- Le travail se fait sur **deux PC** : PC professionnel (`stgadmin`) et PC personnel (`MAbdo`, actuel). Les deux disposent désormais du projet cible, des clés et de la stack de test.
- Le projet cible utilisé sur le PC personnel est `Football-Agent\football-qa`, copie de `Football-QA\MyFinalProject`. `Football-project\MyFinalProject` reste à ne pas utiliser.
- `.env` contient les clés Gemini et Telegram et `REAL_AGENTS_ENABLED=true` ; ne jamais afficher ces valeurs.
- Les agents 4 et 5 (API Automation, UI Automation) sont réels et validés **en réel** (27/27 API, 11/11 UI, 0 anomalie, mission `7e30889c18cd`).
- L’agent 6 (DevOps) reste un stub ; l’agent 7 (reporter) est réel mais le reporting Allure complet relève de la phase 7.
- Chromium est installé sur le PC personnel ; l’agent UI y exécute réellement Playwright.
- Les agents 1 à 3 dépendent du free tier Gemini : une erreur passagère (quota/429) déclenche le repli déterministe sans bloquer la mission ni créer d’anomalie.
- Le test réel du bot Telegram n’a pas encore été exécuté, mais le token est présent.
- Les rapports et preuves de mission sont **locaux** (`reports/missions/`, `workspace/missions/`) et ignorés par Git : leur absence après un clone est normale.
- Aucune nouvelle phase ne doit démarrer sans demande explicite.

---

## 11. Résumé en une phrase

Le socle QA local (baseline, isolation, Manager, gateway Telegram, rapports,
approbation, annulation), la phase 5 (agents 1 à 3 réels avec Gemini
`gemini-3.5-flash`, collection Postman, sondes API limitées à `localhost:8002`)
et la phase 6 (agents 4 et 5 : suite pytest API et scénarios Playwright)
fonctionnent dans un environnement Python 3.12.10 natif, et les **68 tests
passent**. La mission de référence `7e30889c18cd` (10 novembre 2026) a réussi
21/21 sondes, 27/27 tests API et 11/11 scénarios UI avec 0 anomalie, sur une
stack de test saine et avec les clés réelles. Le projet se poursuit à la
phase 7 (agent DevOps et reporting Allure).
