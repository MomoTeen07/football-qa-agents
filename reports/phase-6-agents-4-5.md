# Phase 6 — Agents 4 et 5 (automatisation API et UI)

Date : 9 novembre 2026

## Objectif

Rendre exploitables les deux agents d'automatisation, sans jamais inventer de
résultat ni d'anomalie :

1. **API Automation** — génère une suite pytest à partir de la collection
   Postman et des preuves de la phase 5, puis l'exécute sur la stack de test.
2. **UI Automation** — génère et exécute des scénarios Playwright sur le
   frontend de test isolé.

## État

- Code des agents 4 et 5 : **présent et câblé** dans le Manager et le planner.
- Tests hors ligne : **23 nouveaux tests**, suite complète à **64 tests**.
- Exécution réelle : **à faire sur le PC professionnel**, lorsque le projet
  cible et la stack de test sont disponibles.
- Aucune clé n'est nécessaire pour les tests hors ligne.

## Composants

| Fichier | Rôle |
|---|---|
| `app/agents/phase6.py` | Agents `api_automation` et `ui_automation`, avec repli déterministe. |
| `app/tools/api_suite.py` | Génération de la suite pytest, exécution, parsing JUnit, preuves et anomalies. |
| `app/tools/ui_suite.py` | Génération du script Playwright, exécution, résultats JSON, captures, preuves. |
| `app/agents/stubs.py` | Reporter étendu aux résultats des phases 5 et 6. |
| `scripts/run_phase6_mission.py` | Lanceur explicite d'une mission phase 6. |
| `tests/test_api_suite.py` | 6 tests de la suite API. |
| `tests/test_ui_suite.py` | 9 tests de la suite UI. |
| `tests/test_phase6_agents.py` | 8 tests des agents 4/5 et du reporter. |

## Comportement des agents

### API Automation

- Réutilise la collection Postman de la phase 5 et les preuves
  `probe-results.json`.
- Ne rejoue en pytest que les requêtes **GET sûres** de la collection.
- Génère `workspace/missions/<id>/api-automation/test_api_suite.py`.
- Vérifie d'abord `GET /health` sur `localhost:8002`.
- Si la cible est injoignable : statut `blocked`, **aucune anomalie**.
- Si pytest s'exécute : rapport JUnit, journal expurgé, résultats JSON et
  rapport Markdown.
- Une anomalie n'est créée que pour un test réellement en échec, avec méthode,
  chemin, attendu, obtenu, reproduction et preuve.
- Le rapport JUnit d'une exécution précédente est supprimé avant chaque run.

### UI Automation

- Cible strictement `localhost:5175` (frontend de test) et `localhost:8002`
  (API de test).
- Vérifie le frontend **et** l'API avant de lancer Chromium, pour éviter de
  fausses anomalies applicatives quand la stack est simplement arrêtée.
- Génère `workspace/missions/<id>/ui-automation/run_ui_checks.py`.
- Produit résultats JSON, rapport Markdown et captures d'écran en cas d'échec.
- Un échec technique (navigateur absent, script interrompu) donne `blocked`,
  sans anomalie applicative.
- Les anciens résultats et captures sont supprimés avant chaque run.

### Reporter

Le reporter lit désormais :

- `api/probe-results.json` (phase 5) ;
- `api-automation/api-automation-results.json` (phase 6) ;
- `ui-automation/ui-automation-results.json` (phase 6).

Il agrège les anomalies réellement présentes et conserve les phrases de repli
quand aucune exécution n'a eu lieu.

## Garde-fous

- Aucune mission automatique, aucun scheduler.
- Aucune cible autre que `localhost:8002` et `localhost:5175`.
- L'application réelle (`8001`/`5174`) est refusée avant toute requête.
- Aucun secret affiché ou journalisé ; les journaux sont expurgés.
- Aucune anomalie inventée : cible indisponible ⇒ `blocked`.
- Aucun test destructif : seules des requêtes GET Postman sont rejouées, et
  les favoris de sonde sont nettoyés.

## Dépendance Playwright

`playwright==1.64.1` est ajouté à `requirements.txt`.

Sur le PC professionnel, après installation des dépendances Python :

```powershell
.venv\Scripts\python.exe -m playwright install chromium
```

Sans navigateur installé, l'agent UI renvoie un statut `blocked` et **aucune**
anomalie applicative.

## Validation hors ligne

```powershell
.venv\Scripts\python.exe -m pytest
# 64 passed
```

Les tests utilisent des exécuteurs et des preflights injectés : aucun appel
réseau, aucune stack cible, aucune clé.

## Exécution réelle prévue

Sur le PC professionnel, avec le projet cible et la stack de test démarrée :

```powershell
docker compose -f infra/docker-compose.test.yml -p football-qa-test up --build -d --wait
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe scripts\run_phase6_mission.py
```

Le script affiche `MISSION_ID`, `FINAL_STATUS`, les preuves puis
`API_STATUS`, `API_TESTS`, `API_PASSED`, `API_FAILED`, `API_ANOMALIES` et
l'équivalent UI.

## Pull request

La phase 6 est proposée dans la **PR #1** :
https://github.com/MomoTeen07/football-qa-agents/pull/1

- Branche source : `chore/reconstruct-local-env`
- Branche cible : `main`
- Merge : **humain**, jamais de push direct sur `main`
- Outil : GitHub CLI `gh` 2.103.3, installé via winget et authentifié via le
  navigateur (jeton dans le keyring Windows, jamais dans le dépôt)

Après merge, la reprise sur le PC professionnel se fait depuis `main` :

```powershell
git switch main
git pull --ff-only origin main
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest          # attendu : 64 passed
```

## Limites connues

- La validation réelle API/UI n'a pas encore été exécutée sur cette machine
  (projet cible absent).
- Le reporting Allure complet reste prévu en phase 7.
- L'agent DevOps (branche + PR) reste un stub de planification.
