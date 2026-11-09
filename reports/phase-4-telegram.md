# Phase 4 — Connexion Telegram

Date : 9 novembre 2026

## Composants créés

- `app/telegram/__init__.py` : package Telegram.
- `app/telegram/auth.py` : allowlist stricte par `user_id`.
- `app/telegram/gateway.py` : bot en polling, sans scheduler.
- `tests/test_telegram_auth.py` : tests de l'allowlist.
- `tests/test_telegram_gateway.py` : tests du gateway, de l'absence de mission automatique et de l'absence de `JobQueue`.

## Commandes disponibles

| Commande | Comportement |
|---|---|
| `/start` | Présentation du bot et rappel des commandes. |
| `/help` | Aide détaillée. |
| `/status <mission_id>` | Statut de la mission, tâches et dernier événement. |
| `/missions` | Liste des 10 missions les plus récentes. |
| `/approve <mission_id>` | Approbation explicite puis exécution. |
| `/stop <mission_id>` | Demande d'annulation. |
| Texte libre | Création puis exécution d'une mission, uniquement sur message explicite. |

Si une mission nécessite une approbation, le gateway répond avec le motif et
n'exécute pas la mission. L'utilisateur doit envoyer explicitement
`/approve <mission_id>`.

## Allowlist stricte

- Chaque update passe d'abord par un handler de garde dans le groupe `-1`.
- `is_allowed` refuse un `user_id` absent, vide ou différent.
- Un utilisateur refusé reçoit uniquement le message neutre `Accès refusé.`
- Aucun détail sur la configuration, l'identifiant autorisé ou les secrets
  n'est révélé.
- Le gateway refuse de démarrer si `TELEGRAM_ALLOWED_USER_ID` est vide.

## Absence de scheduler

- Utilisation exclusive du polling via `Application.run_polling`.
- Aucun `JobQueue`, aucun cron, aucun webhook, aucune mission planifiée.
- Aucune mission n'est créée à l'import du module, au démarrage du bot ou
  sans message utilisateur explicite.
- Le test `test_gateway_has_no_job_queue` vérifie que `application.job_queue`
  vaut `None`.

## Exécution des missions

Le Manager est synchrone. Toutes les opérations de mission sont exécutées hors
de la boucle asyncio avec `asyncio.to_thread` :

- création d'une mission ;
- exécution ou approbation ;
- annulation ;
- consultation du statut et de la liste des missions.

Un seul `Manager` est créé par processus par `ManagerProvider`, protégé par un
verrou `threading.Lock`. Un verrou `asyncio.Lock` empêche deux exécutions de
mission simultanées. L'annulation n'attend pas ce verrou, afin de pouvoir
interrompre une mission en cours.

## Validation

```powershell
.venv\Scripts\python.exe -m pytest
# 23 passed
```

Détail :

| Catégorie | Nombre |
|---|---:|
| Tests existants du socle Manager | 5 |
| Tests allowlist Telegram | 5 |
| Tests gateway et absence de mission automatique | 13 |
| **Total** | **23** |

Le warning `PTBUserWarning: No JobQueue set up` est attendu : le test
`test_gateway_has_no_job_queue` le capture et vérifie qu'aucune file de tâches
n'est configurée.

Vérification du point d'entrée avec le token vide :

```powershell
.venv\Scripts\python.exe -m app.telegram.gateway
# TELEGRAM_BOT_TOKEN est vide dans .env : le bot Telegram ne démarre pas.
# exit code 2
```

Le processus s'arrête avant de créer un Manager ou une mission.

## Limites actuelles

- `TELEGRAM_BOT_TOKEN` est vide : le bot ne peut pas être testé réellement.
- `GEMINI_API_KEY` est vide : cela ne bloque pas la phase 4, car le gateway
  n'effectue encore aucun appel LLM. L'intégration Gemini concerne la phase 5.
- Les tests réels de bout en bout avec Telegram restent à faire après
  renseignement du token dans `.env`.
- Les agents restent des stubs de planification : aucun test réel n'est exécuté
  et aucune anomalie n'est déclarée.

## Garde-fous vérifiés

- Aucune mission automatique.
- Aucun scheduler.
- Allowlist vérifiée sur chaque update.
- Aucun secret affiché ni journalisé, y compris lorsqu'un token est refusé par
  Telegram.
- Aucune écriture dans la base réelle `footballqa`.
- La base SQLite de pilotage reste locale.
- Une mission sensible reste bloquée tant qu'elle n'est pas approuvée.
