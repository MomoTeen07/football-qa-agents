# PROJECT_CONTEXT — Football QA Agents

Date du point de reprise : 9 novembre 2026  
Dernière action terminée : phase 5 (agents 1 à 3 réels, Gemini, Postman, sondes API) — **41 tests sur 41 réussis**, mission `b745b4a199b7` avec 21/21 sondes réussies et 0 anomalie.  
État global : **phases 1 à 5 terminées côté code ; test réel du bot Telegram encore optionnel**. Le projet n’est pas terminé.

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
- Git : branche + PR uniquement, jamais de push direct sur `main` ; merge humain.
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

- L’application réelle est dans `C:\Users\stgadmin\Desktop\football-qa`.
- Le projet QA est dans `C:\Users\stgadmin\Desktop\football-qa-agents`.
- La stack de test utilise `MOCK_FOOTBALL_API=true`.
- La stack de test était démarrée au moment du point de reprise.
- La base réelle est restée intacte : **5 utilisateurs / 2 favoris**.
- La base de test contient **2 utilisateurs / 0 favoris**.
- Comptes de test : `qa.user1@example.com` et `qa.user2@example.com`.
- Le validateur d’email de l’application refuse les domaines `.test` ; utiliser `example.com`.

---

## 3. État d’avancement

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
- [ ] Test réel du bot désormais possible (token présent), mais non exécuté.

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
- [x] Suite complète : **41 tests réussis**.
- [x] Mission réelle `b745b4a199b7` : 21/21 sondes, 0 anomalie.
- [x] Documentation : `reports/phase-5-agents-1-3.md`.
- [x] mise à jour `README.md` (phase 5).
- [ ] Test réel du bot Telegram avec le token désormais présent (optionnel).

### Phases restantes

- [ ] **Phase 6 — agents 4 et 5** : automatisation API pytest et UI Playwright réelles.
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
QA Analyst  Test Designer  API Tester   Agents 4–7    QA Reporter
(Gemini)    (Gemini)       (OpenAPI +   (stubs)       (preuves réelles)
                           Postman +
                           sondes HTTP)
```

- Le **Manager** crée la mission, planifie les tâches, applique
  l’approbation/l’annulation et publie les événements.
- Le **graphe LangGraph** exécute les tâches dans l’ordre des dépendances et
  transmet au reporter les résultats et preuves de chaque tâche.
- Les **agents 1 à 3** sont réels depuis la phase 5 ; les **agents 4 à 7**
  restent des stubs de planification.
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
  - Le `QAReporterAgent` lit `probe-results.json` et n’énonce que des
    anomalies réellement présentes.
  - Les agents 4 à 7 restent inchangés.

- `app/orchestrator/manager.py`
  - Injecte `GeminiClient` et `ApiProbe` dans les agents réels.

- `app/orchestrator/graph.py`
  - Le contexte du reporter transporte désormais `result` et `evidence`.

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
# 41 passed
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
| `requirements.txt` | Dépendances Python, Telegram inclus |
| `pyproject.toml` | Configuration pytest |
| `PROJECT_CONTEXT.md` | Ce point de reprise |
| `app/__init__.py` | Package principal |
| `app/config.py` | Settings Pydantic, chemins, secrets |
| `app/domain/models.py` | Mission, Task, Event, AgentResult, statuts |
| `app/store/sqlite_store.py` | Stockage SQLite missions/tâches/événements |
| `app/events/bus.py` | EventBus réel avec abonnés |
| `app/agents/base.py` | Interface `BaseAgent` |
| `app/agents/phase5.py` | Agents 1 à 3 réels (Gemini, OpenAPI, Postman, sondes) |
| `app/agents/stubs.py` | Agents 4 à 7 (stubs) et reporter basé sur les preuves |
| `app/llm/__init__.py` | Package d’intégration LLM |
| `app/llm/gemini.py` | Client Gemini free tier REST, sans fuite de clé |
| `app/tools/__init__.py` | Package des outils réels |
| `app/tools/workspace.py` | Écriture UTF-8 des preuves de mission |
| `app/tools/openapi_postman.py` | Analyse OpenAPI et génération Postman |
| `app/tools/api_probe.py` | Sondes API réelles, garde-fou 8002, preuves, anomalies |
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
| `tests/test_gemini_client.py` | 5 tests du client Gemini (dont absence de fuite de clé) |
| `tests/test_openapi_postman.py` | 3 tests OpenAPI et Postman |
| `tests/test_api_probe.py` | 4 tests des sondes, du garde-fou et des anomalies |
| `tests/test_phase5_agents.py` | 6 tests des agents phase 5 et du reporter |
| `infra/docker-compose.test.yml` | Stack de test isolée |
| `scripts/seed_test_data.py` | Création des comptes de test |
| `scripts/run_phase5_mission.py` | Lanceur explicite d’une mission phase 5 |
| `postman/collections/football-qa.json` | Collection Postman réelle (11 requêtes) |
| `postman/environments/football-qa-test.json` | Environnement Postman de test |
| `reports/baseline.md` | Baseline |
| `reports/phase-2-isolation.md` | Validation isolation |
| `reports/phase-3-manager-core.md` | Validation socle Manager |
| `reports/phase-4-telegram.md` | Validation connexion Telegram |
| `reports/phase-5-agents-1-3.md` | Validation phase 5 |
| `reports/missions/4e1c01636615.md` | Rapport de mission de démonstration |
| `reports/missions/b745b4a199b7.md` | Rapport de la mission phase 5 de référence |
| `workspace/missions/b745b4a199b7/` | Preuves de la mission phase 5 |
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
- **Git** : branche + PR uniquement, merge humain.
- **Agents actuels** : agents 1 à 3 réels ; agents 4 à 7 encore en stubs. Aucune anomalie inventée.
- **Sondes API** : cible strictement limitée à `localhost`/`127.0.0.1:8002` ; l’application réelle `8001` est refusée.
- **Anomalies** : uniquement sur échec réel, avec reproduction et extrait de preuve.
- **Postman** : collection générée depuis l’OpenAPI réel, pas de collection écrite à la main.
- **Email de test** : `example.com` car `.test` est refusé par le validateur.

---

## 7. Configuration, secrets et restes à faire

`.env` est présent et ignoré par Git. Il contient les secrets locaux. Aucune
valeur de secret n’est reproduite dans ce document.

État vérifié au moment du point de reprise :

| Variable | État |
|---|---|
| `TELEGRAM_ALLOWED_USER_ID` | renseigné dans `.env` (identifiant non reproduit ici) |
| `TELEGRAM_BOT_TOKEN` | **présent** dans `.env` ; bot validé par `getMe` (`Quaresma_QA_bot`) |
| `GEMINI_API_KEY` | **présent** dans `.env` ; API et génération validées |
| `LLM_MODEL` | `gemini-3.5-flash` |
| `REAL_AGENTS_ENABLED` | `true` |
| `TEST_API_URL` | `http://localhost:8002` |
| `TEST_UI_URL` | `http://localhost:5175` |
| `TEST_USER1_EMAIL` / `TEST_USER2_EMAIL` | comptes de test locaux |
| `GROQ_API_KEY` / `MISTRAL_API_KEY` | non utilisés par la phase 5 |

Historique utile :

- Les deux clés avaient d’abord été déposées dans
  `C:\Users\stgadmin\Desktop\football-qa\.env` (application cible), puis
  copiées dans `football-qa-agents\.env` sans affichage.
- Ne jamais afficher, journaliser ou coller ces valeurs dans le chat, un
  rapport ou une preuve.

### Configuration Telegram restant à effectuer

- Aucune configuration obligatoire ne reste : le token et l’allowlist sont
  présents.
- Il reste seulement le **test réel du bot** (démarrage du gateway, `/start`,
  texte libre, `/status`, `/approve`, `/stop`). Ce test n’a pas été exécuté
  pendant la phase 5 et n’est pas nécessaire à la validation des agents.
- Vérifier que le token n’a jamais été publié ; en cas de doute, le régénérer
  via BotFather et mettre à jour `.env` sans afficher la nouvelle valeur.

### Configuration Gemini restant à effectuer

- Aucune configuration obligatoire ne reste : la clé est présente et
  `gemini-3.5-flash` répond.
- Surveiller le quota du free tier ; en cas de dépassement, le repli
  déterministe s’applique sans bloquer la mission.
- Ne pas revenir à `gemini-2.5-flash` ni `gemini-2.5-flash-lite` : HTTP 404
  pour ce compte.
- Ne jamais exposer la clé dans une URL de rapport, un log ou une preuve.

---

## 8. Comment reprendre dans une nouvelle conversation

### Étape 0 — vérifier l’environnement

```powershell
cd C:\Users\stgadmin\Desktop\football-qa-agents

# Tests du système QA
.venv\Scripts\python.exe -m pytest

# Stack de test
docker compose -f infra/docker-compose.test.yml -p football-qa-test ps
```

Si la stack n’est pas démarrée :

```powershell
docker compose -f infra/docker-compose.test.yml -p football-qa-test up --build -d --wait
```

Vérifier :

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8002/health
Invoke-WebRequest -UseBasicParsing http://localhost:5175/
```

Attendu : `41 passed` et stack `healthy` sur `8002`, `5434` et `5175`.
Ne jamais sonder `8001` avec les outils du projet.

### Étape 1 — vérifier l’état livré

```powershell
# Rapport de la mission de référence
Get-Content reports\missions\b745b4a199b7.md

# Preuves de la mission
Get-ChildItem workspace\missions\b745b4a199b7 -Recurse

# Collection Postman
Get-Content postman\collections\football-qa.json -TotalCount 20
```

Attendu : 21/21 sondes, 0 anomalie, 11 requêtes Postman.

### Étape 2 — relancer une mission phase 5 (optionnel)

```powershell
.venv\Scripts\python.exe scripts\run_phase5_mission.py
```

Le script refuse de s’exécuter si `REAL_AGENTS_ENABLED=false`. Il crée une
mission explicite, exécute les agents 1 à 3, écrit les preuves et affiche
`PROBE_CHECKS`, `PROBE_PASSED`, `PROBE_ANOMALIES`.

### Étape 3 — tester réellement le bot Telegram (optionnel)

```powershell
.venv\Scripts\python.exe -m app.telegram.gateway
```

Puis, depuis le compte autorisé : `/start`, un texte libre, `/status <id>`,
`/approve <id>` si demandé, `/stop <id>`. Aucun scheduler ne doit démarrer.

### Étape 4 — prochaine phase de développement

**Phase 6 — agents 4 et 5** : automatisation API pytest et UI Playwright
réelles, en réutilisant les preuves et la collection Postman de la phase 5.
Ne pas démarrer cette phase sans demande explicite.

### En cas de problème connu

| Symptôme | Cause probable | Action |
|---|---|---|
| `Gemini a répondu HTTP 404` | modèle obsolète | garder `LLM_MODEL=gemini-3.5-flash` |
| `GEMINI_API_KEY absente` | clé dans le mauvais `.env` | vérifier `football-qa-agents\.env`, ne pas afficher la valeur |
| `UnsafeTargetError` | cible autre que `localhost:8002` | corriger `TEST_API_URL`, ne pas viser `8001` |
| tests lents ou appels réels | `REAL_AGENTS_ENABLED=true` dans l’environnement | les tests forcent déjà `false` ; vérifier les overrides |
| accents illisibles en console | rendu PowerShell | les fichiers sont UTF-8 ; lire avec Python si besoin |

---

## 9. Commandes utiles

```powershell
# Tests du système QA
.venv\Scripts\python.exe -m pytest

# Mission réelle phase 5 (explicite, sur la stack de test)
.venv\Scripts\python.exe scripts\run_phase5_mission.py

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
- Le projet `football-qa-agents` n’est **pas encore initialisé en Git**.
- Les agents 4 à 7 sont encore des stubs de planification.
- Les agents 1 à 3 sont réels mais dépendent de la stack de test et du free tier Gemini ; un repli déterministe reste actif en cas d’indisponibilité.
- Le test réel du bot Telegram n’a pas été exécuté pendant la phase 5.
- Aucune nouvelle phase ne doit démarrer sans demande explicite.

---

## 11. Résumé en une phrase

Le socle QA local (baseline, isolation, Manager, gateway Telegram, rapports,
approbation, annulation) et la phase 5 (agents 1 à 3 réels avec Gemini
`gemini-3.5-flash`, collection Postman générée depuis l’OpenAPI réel, sondes
API limitées à `localhost:8002`) fonctionnent et les 41 tests passent ; la
mission de référence `b745b4a199b7` a réussi 21/21 sondes avec 0 anomalie, et
la suite du projet reprend à la phase 6 (agents 4 et 5).
