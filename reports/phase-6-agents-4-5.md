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
- Tests hors ligne : **23 nouveaux tests**, suite complète à **65 tests**.
- Exécution réelle : **faite le 10 novembre 2026** (mission `7e30889c18cd`),
  sur une stack de test saine et avec les clés réelles.
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
# 65 passed
```

Les tests utilisent des exécuteurs et des preflights injectés : aucun appel
réseau, aucune stack cible, aucune clé.

## Exécution réelle — 10 novembre 2026

Machine : PC personnel (`MAbdo`), projet cible
`C:\Users\MAbdo\Desktop\Football-Agent\football-qa`, stack `football-qa-test`
saine, Chromium installé, `REAL_AGENTS_ENABLED=true`.

```powershell
docker compose -f infra/docker-compose.test.yml -p football-qa-test up --build -d --wait
.venv\Scripts\python.exe scripts\seed_test_data.py
.venv\Scripts\python.exe scripts\run_phase6_mission.py
```

Mission de référence `7e30889c18cd` :

| Vérification | Résultat |
|---|---|
| Sondes API (phase 5) | 21/21, 0 anomalie |
| Tests pytest API générés | 27/27 réussis |
| Scénarios Playwright | 11/11 réussis |
| Anomalies applicatives | 0 |
| Statut de la mission | `completed` |

Les rapports et preuves sont locaux :
`workspace/missions/7e30889c18cd/` et `reports/missions/7e30889c18cd.md`.

### Défauts d'outillage trouvés et corrigés pendant cette exécution

1. **Suite pytest générée non collectable** — les cas Postman étaient injectés
   avec `json.dumps`, donc `false`/`true`/`null` apparaissaient dans un fichier
   Python. Résultat observé : `NameError: name 'false' is not defined` et un
   unique faux échec de collecte. Correction : `pformat` (littéraux Python).
   Vérifié après correctif : **27/27**.
2. **Scénario de connexion UI** — le scénario enchaînait sur `/login` après la
   redirection `/favorites → /login`, dont `history.state.from` renvoie
   légitimement vers `/favorites` (comportement correct de l'application).
   Correction : repasser par une page publique avant `/login`. Vérifié après
   correctif : **11/11**.
3. **Identifiant d'environnement Postman instable** — UUID aléatoire à chaque
   génération, donc diff parasite sur un fichier versionné. Correction :
   `uuid5` déterministe.

Aucun de ces défauts n'était une anomalie applicative : ils sont corrigés côté
outillage QA, sans modifier l'application cible.

## Pull request

La phase 6 est proposée dans la **PR #1** :
https://github.com/MomoTeen07/football-qa-agents/pull/1

- Branche source : `chore/reconstruct-local-env`
- Branche cible : `main`
- Merge : jamais de push direct sur `main` ; la PR est fusionnée après
  vérification (validation humaine plus requise depuis le 10 novembre 2026)
- Outil : GitHub CLI `gh` 2.103.3, installé via winget et authentifié via le
  navigateur (jeton dans le keyring Windows, jamais dans le dépôt)

Après merge, la reprise se fait depuis `main` :

```powershell
git switch main
git pull --ff-only origin main
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest          # attendu : 65 passed
```

La validation réelle et les correctifs associés sont proposés dans la **PR #4**
(`fix/phase6-real-run`, 10 novembre 2026).

## Limites connues

- Le test réel du bot Telegram n'a pas encore été exécuté (token présent).
- Le reporting Allure complet reste prévu en phase 7.
- L'agent DevOps (branche + PR) reste un stub de planification.
- Les missions réelles utilisent le free tier Gemini : une erreur de quota
  déclenche le repli déterministe, sans anomalie applicative.

> Limites historiques de la phase 6. Le reporting Allure et l'agent DevOps ont
> depuis été livrés par la phase 7 (PR #11, 11 novembre 2026) ; voir
> `reports/phase-7-agents-6-7.md`.
