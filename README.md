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

## État d'avancement

- [x] Phase 1 — baseline de l'application existante
- [x] Phase 2 — stack de test isolée
- [x] Phase 3 — socle du Manager
- [x] Phase 4 — connexion Telegram
- [x] Phase 5 — agents 1 à 3
- [ ] Phase 6 — agents 4 et 5
- [ ] Phase 7 — agents 6 et 7
- [ ] Phase 8 — bureau virtuel
- [ ] Phase 9 — durcissement
