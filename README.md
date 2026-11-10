# Football QA Agents

[![Tests](https://github.com/MomoTeen07/football-qa-agents/actions/workflows/tests.yml/badge.svg)](https://github.com/MomoTeen07/football-qa-agents/actions/workflows/tests.yml)

Système multi-agents QA pour tester l'application locale `football-qa`.

## Principes

- Fonctionnement uniquement à la demande, déclenché par Telegram.
- Aucun test périodique, aucun planificateur, aucune mission automatique.
- Base de données de test isolée : jamais d'écriture dans la base réelle.
- Secrets stockés dans `.env`, exclus de Git.
- Rapports et preuves conservés localement.

## Suivi des modifications

- **`CHANGELOG.md`** est la source de vérité chronologique : chaque
  modification notable y ajoute une entrée datée.
- Toute modification doit aussi mettre à jour **`README.md`** et
  **`PROJECT_CONTEXT.md`**. Une PR n'est pas terminée si l'un des trois fichiers
  est en retard.
- Dernière entrée : **0.6.5 — Test réel du bot Telegram**.

## Intégration continue

`.github/workflows/tests.yml` exécute `python -m pytest` sur chaque pull
request et sur chaque push vers `main` (Python 3.12, sans clé, sans réseau).
Comme les PR sont fusionnées par l'agent, ce workflow est le garde-fou avant
fusion ; il peut aussi être lancé manuellement (`workflow_dispatch`).

## Structure

```text
.github/              CI GitHub Actions (pytest sur chaque PR)
CHANGELOG.md          Historique daté des modifications
app/                  Manager, agents, outils, événements
app/llm/              Client Gemini free tier
app/tools/            OpenAPI, Postman, sondes API, workspace
office/               Bureau virtuel 2D
postman/              Collections et environnements Postman
infra/                Stack Docker de test
scripts/              Scripts de préparation et de mission
workspace/            Espaces de travail par mission
reports/              Rapports de baseline, Allure et synthèses
tests/                Tests du système multi-agents
```

## État de l'environnement local (10 novembre 2026)

- Python **3.12.10** natif (obligatoire : `requires-python >= 3.12`).
- `.venv` recréé et dépendances `requirements.txt` installées.
- `.env` complété : **clés Gemini et Telegram disponibles**,
  `REAL_AGENTS_ENABLED=true` → agents réels actifs. Les valeurs ne sont
  jamais affichées ni versionnées.
- `.venv\Scripts\python.exe -m pytest` → **69 passed**.
- `playwright==1.64.1` installé et **Chromium présent** dans
  `%LOCALAPPDATA%\ms-playwright` : l'exécution UI réelle est possible.
- Projet cible `football-qa` présent à côté du projet QA
  (`C:\Users\MAbdo\Desktop\Football-Agent\football-qa`).
- Stack de test `football-qa-test` construite et saine (`8002`/`5175`/`5434`).
- **GitHub CLI** `gh` 2.103.3 installé via winget et authentifié via le
  navigateur ; le jeton reste dans le keyring Windows, jamais dans le projet.

Sans clés, tous les tests passent et les agents basculent sur leur repli
déterministe. Pour réactiver Gemini et Telegram, renseigner
`GEMINI_API_KEY` et `TELEGRAM_BOT_TOKEN` dans `.env`, sans jamais les afficher.

## Deux machines de travail

Le projet est utilisé sur deux PC. Un élément manquant sur l'un n'est pas une
régression : il faut d'abord identifier la machine.

| Élément | PC professionnel | PC personnel |
|---|---|---|
| Utilisateur | `stgadmin` | `MAbdo` |
| Projet cible `football-qa` | présent | présent |
| Stack de test Docker | opérationnelle | opérationnelle |
| Clés Gemini / Telegram | présentes dans `.env` | présentes dans `.env` |
| Tests unitaires | à jour après `git pull` sur `main` | **69 passed** |

Les deux PC permettent désormais les missions réelles. Sur le PC personnel, le
projet cible est une copie de travail du dépôt `MyFinalProject` ; en cas de
doute sur la version, comparer les deux dossiers avant de conclure à une
régression.

## Pull request et reprise sur le PC professionnel

La phase 6 a été **fusionnée** via la **PR #1** (merge commit `992d007`,
9 novembre 2026) : `main` contient l'automatisation API/UI et le reporter
étendu. Sa **validation en réel** et les correctifs associés arrivent par la
**PR #4** (`fix/phase6-real-run`, 10 novembre 2026).

### Depuis `main` (recommandé)

```powershell
cd C:\Users\stgadmin\Desktop\football-qa-agents
git status                                  # vérifier l'absence de modifications locales
git switch main
git pull --ff-only origin main

.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest          # attendu : 69 passed
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
- Ne pas pousser sur `main` : la fusion se fait par pull request, fusionnée par
  l'agent après vérification (plus de validation humaine depuis le
  10 novembre 2026).
- **GitHub CLI** (`gh` 2.103.3) est installé sur le PC personnel pour créer les
  PR ; l'authentification est stockée dans le keyring Windows. Aucun secret
  n'est documenté ni journalisé.

## Prérequis pour les missions réelles

Le compose de test référence `../../football-qa/backend` et
`../../football-qa/frontend`, c'est-à-dire un dossier `football-qa` **voisin**
de `football-qa-agents`. Sur le PC personnel, la copie de travail se trouve en
`C:\Users\MAbdo\Desktop\Football-Agent\football-qa` (copiée depuis
`C:\Users\MAbdo\Desktop\Football-QA\MyFinalProject`).

Sans ce dossier, la stack `8002`/`5175` ne peut pas être construite et les
missions réelles sont bloquées. Le compose ne modifie jamais la base réelle :
il crée son propre volume PostgreSQL sur `5434`.

## Stack de test

| Service | URL locale |
|---|---|
| Frontend de test | http://localhost:5175 |
| API de test | http://localhost:8002 |
| PostgreSQL de test | localhost:5434 |
| Documentation API | http://localhost:8002/docs |

La stack utilise `MOCK_FOOTBALL_API=true` pour des tests déterministes.

## Commandes prévues

```powershell
# Créer l'environnement Python (une fois)
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Créer la configuration locale sans secrets
Copy-Item .env.example .env

# Lancer les tests du système QA
.venv\Scripts\python.exe -m pytest

# Installer Chromium (nécessaire uniquement pour l'exécution UI réelle)
.venv\Scripts\python.exe -m playwright install chromium

# Lancer explicitement une mission phase 6 API + UI
.venv\Scripts\python.exe scripts\run_phase6_mission.py

# Démarrer la stack de test
docker compose -f infra/docker-compose.test.yml -p football-qa-test up --build -d --wait

# Vérifier l'état
docker compose -f infra/docker-compose.test.yml -p football-qa-test ps

# Arrêter la stack de test
docker compose -f infra/docker-compose.test.yml -p football-qa-test down
```

## Telegram

Le bot fonctionne uniquement en polling, sur message explicite d'un utilisateur
présent dans l'allowlist. Aucun scheduler ni mission automatique.

```powershell
# Démarrer le bot après avoir renseigné TELEGRAM_BOT_TOKEN dans .env
.venv\Scripts\python.exe -m app.telegram.gateway
```

| Commande | Rôle |
|---|---|
| `/start` | Présentation et rappel des commandes |
| `/help` | Aide |
| `/status <mission_id>` | Statut, tâches et dernier événement |
| `/missions` | Missions récentes |
| `/approve <mission_id>` | Approbation explicite puis exécution |
| `/stop <mission_id>` | Demande d'annulation |
| Texte libre | Création puis exécution d'une mission |

Validation **en réel** (10 novembre 2026, bot `@Quaresma_QA_bot`, sans
`409 Conflict`) :

- `/start`, `/help`, `/status <id>`, `/missions`, `/approve <id>`,
  `/stop <id>` répondent conformément ;
- un texte libre a créé **et exécuté** une mission réelle :
  `8c568cce0ef4`, 6/6 tâches, 21/21 sondes, 27/27 tests API,
  11/11 scénarios UI, **0 anomalie** ;
- une instruction sensible (`… dans Jira`, mission `8d7a1f40274d`) est restée
  à `created` sans exécution jusqu'à `/approve` ;
- `/stop c5d08e7742e2` a annulé la mission, et une approbation tardive ne l'a
  pas relancée (`cancelled`) ;
- aucun scheduler, aucun `JobQueue`, aucun `409` ; logs locaux dans `logs/`
  (ignoré par Git) avec le jeton masqué (`[redacted]`).

Détail : `reports/phase-4-telegram.md`. Reste à rejouer : le refus d'un
**compte non autorisé** (« Accès refusé. »), faute de second compte pendant la
session.

Les secrets restent dans `.env`, ignoré par Git. Ne jamais coller un secret dans
une conversation ou un rapport.

## Agents réels (phase 5)

Les agents 1 à 3 disposent d'une implémentation réelle, activée par
`REAL_AGENTS_ENABLED=true` :

- **QA Analyst** et **Test Designer** : analyse enrichie par Gemini free tier,
  avec repli déterministe si la clé est absente ou l'appel échoue.
- **API Tester** : analyse de l'OpenAPI réel, génération de la collection
  Postman et exécution de sondes HTTP réelles.

Modèle par défaut : `gemini-3.5-flash` (`LLM_MODEL` dans `.env`).

Les réponses `429` et `5xx` du free tier sont retentées (3 tentatives, backoff
1 s puis 2 s). Si toutes échouent, le repli déterministe s'applique sans
bloquer la mission.

Les sondes sont strictement limitées à la stack de test locale
(`http://localhost:8002`). Toute autre cible, notamment l'application réelle
sur `8001`, est refusée avant la moindre requête. Les preuves et les anomalies
reproductibles sont écrites dans `workspace/missions/<mission_id>/api/`.

```powershell
# Lancer explicitement une mission phase 5 sur la stack de test
.venv\Scripts\python.exe scripts\run_phase5_mission.py

# Exécuter toute la suite de tests du système
.venv\Scripts\python.exe -m pytest
```

Résultat de référence : mission `b745b4a199b7`, 21/21 sondes réussies,
0 anomalie. Voir `reports/phase-5-agents-1-3.md`.

## Automatisation API et UI (phase 6)

Les agents 4 et 5 sont réels et activés par `REAL_AGENTS_ENABLED=true` :

- **API Automation** : génère une suite pytest à partir des GET sûrs de la
  collection Postman et des preuves de la phase 5, l'exécute sur
  `http://localhost:8002`, puis produit un rapport JUnit, un journal expurgé,
  un JSON et un Markdown.
- **UI Automation** : génère et exécute des scénarios Playwright/Chromium sur
  `http://localhost:5175`, avec préflight du frontend **et** de l'API, résultats
  JSON, rapport Markdown et captures en cas d'échec.

Garde-fous :

- cible API limitée à `localhost:8002`, cible UI limitée à `localhost:5175` ;
- l'application réelle (`8001`/`5174`) est refusée avant toute requête ;
- cible ou navigateur indisponible ⇒ statut `blocked`, **aucune anomalie** ;
- aucune preuve d'une exécution précédente n'est réutilisée.

Le reporter lit désormais les preuves des phases 5 et 6 et n'agrège que les
anomalies réellement présentes.

```powershell
# Installer Chromium puis lancer une mission phase 6 explicite
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe scripts\run_phase6_mission.py
```

Validation **en réel** (10 novembre 2026, mission `7e30889c18cd`) :

| Vérification | Résultat |
|---|---|
| Sondes API (phase 5) | 21/21, 0 anomalie |
| Tests pytest API générés | 27/27, 0 échec |
| Scénarios Playwright | 11/11, 0 échec |
| Anomalies applicatives | 0 |

Suite du système : **69 tests passent**. Voir `reports/phase-6-agents-4-5.md`
et `PROJECT_CONTEXT.md` pour le détail des correctifs de cette validation
(littéraux Python dans la suite générée, scénario de connexion, identifiant
Postman stable).

## État d'avancement

- [x] Environnement local complet sur le PC personnel — Python 3.12.10, `.venv`, `.env` avec clés, Chromium, stack de test, **69 tests passent**
- [x] Journal des modifications `CHANGELOG.md` et règle de mise à jour documentaire
- [x] Phase 1 — baseline de l'application existante
- [x] Phase 2 — stack de test isolée
- [x] Phase 3 — socle du Manager
- [x] Phase 4 — connexion Telegram (code **et test réel** le 10 novembre 2026 : commandes validées, mission `8c568cce0ef4` à 0 anomalie, approbation et annulation vérifiées, aucun scheduler)
- [x] Phase 5 — agents 1 à 3
- [x] Phase 6 — agents 4 et 5 (code + validation hors ligne **et** exécution réelle : 27/27 API, 11/11 UI, 0 anomalie)
- [ ] Phase 7 — agents 6 et 7
- [ ] Phase 8 — bureau virtuel
- [ ] Phase 9 — durcissement
