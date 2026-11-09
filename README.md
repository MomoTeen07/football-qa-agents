# Football QA Agents

Système multi-agents QA pour tester l'application locale `football-qa`.

## Principes

- Fonctionnement uniquement à la demande, déclenché par Telegram.
- Aucun test périodique, aucun planificateur, aucune mission automatique.
- Base de données de test isolée : jamais d'écriture dans la base réelle.
- Secrets stockés dans `.env`, exclus de Git.
- Rapports et preuves conservés localement.

## Structure

```text
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

## État de l'environnement local (9 novembre 2026)

- Python **3.12.10** natif (obligatoire : `requires-python >= 3.12`).
- `.venv` recréé et dépendances `requirements.txt` installées.
- `.env` recréé depuis `.env.example` : **clés Gemini/Telegram vides**,
  `REAL_AGENTS_ENABLED=false` → repli déterministe.
- `.venv\Scripts\python.exe -m pytest` → **64 passed**.
- `playwright==1.64.1` installé ; le navigateur Chromium n'est **pas** installé
  sur ce PC (nécessaire uniquement à l'exécution UI réelle).

Sans clés, les 64 tests passent et les agents basculent sur leur repli
déterministe. Pour réactiver Gemini et Telegram, renseigner
`GEMINI_API_KEY` et `TELEGRAM_BOT_TOKEN` dans `.env`, sans jamais les afficher.

## Deux machines de travail

Le projet est utilisé sur deux PC. Un élément manquant sur l'un n'est pas une
régression : il faut d'abord identifier la machine.

| Élément | PC professionnel | PC personnel (actuel) |
|---|---|---|
| Utilisateur | `stgadmin` | `MAbdo` |
| Projet cible `football-qa` | présent | **absent** |
| Stack de test Docker | opérationnelle | non construite |
| Clés Gemini / Telegram | présentes dans `.env` | **absentes** |
| Tests unitaires | 41 passed (phase 5, à resynchroniser) | **64 passed** |

Le PC personnel permet le développement hors ligne et les tests unitaires ;
les missions réelles se font sur le PC professionnel ou après copie du projet
cible et des clés.

## Prérequis pour les missions réelles

Le projet cible à jour (`football-qa`) **n'est pas présent** sur le PC personnel
actuel. `C:\Users\MAbdo\Desktop\Football-project\MyFinalProject` n'est **pas**
la bonne version et ne doit pas être utilisé.

Le compose de test référence `../../football-qa/backend` et
`../../football-qa/frontend` : sans ce dossier, la stack `8002`/`5175` ne peut
pas être construite et les missions réelles sont bloquées.

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

Validation hors ligne : **64 tests passent**. L'exécution réelle API + UI reste
à faire sur le PC professionnel. Voir `reports/phase-6-agents-4-5.md`.

## État d'avancement

- [x] Environnement local reconstruit sur le PC personnel — Python 3.12.10, `.venv`, `.env` sans clés, **64 tests passent**
- [x] Phase 1 — baseline de l'application existante
- [x] Phase 2 — stack de test isolée
- [x] Phase 3 — socle du Manager
- [x] Phase 4 — connexion Telegram
- [x] Phase 5 — agents 1 à 3
- [x] Phase 6 — agents 4 et 5 (code + validation hors ligne ; exécution réelle à faire sur le PC professionnel)
- [ ] Phase 7 — agents 6 et 7
- [ ] Phase 8 — bureau virtuel
- [ ] Phase 9 — durcissement
