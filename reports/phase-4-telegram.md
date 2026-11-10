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

> Chiffres du 9 novembre 2026. Au 10 novembre 2026, après les phases 5 et 6 et
> le test réel du bot, la suite compte **72 tests** (dont **17** pour
> `tests/test_telegram_gateway.py`).

Vérification du point d'entrée avec le token vide :

```powershell
.venv\Scripts\python.exe -m app.telegram.gateway
# TELEGRAM_BOT_TOKEN est vide dans .env : le bot Telegram ne démarre pas.
# exit code 2
```

Le processus s'arrête avant de créer un Manager ou une mission.

## Limites actuelles

- ~~`TELEGRAM_BOT_TOKEN` est vide : le bot ne peut pas être testé réellement.~~
  **Levée le 10 novembre 2026** : le jeton est renseigné et le bot a été validé
  en réel (voir la section suivante).
- ~~Les tests réels de bout en bout avec Telegram restent à faire après
  renseignement du token dans `.env`.~~ **Levée le 10 novembre 2026.**
- `GEMINI_API_KEY` est désormais renseignée : les agents 1 à 3 sont réels
  (phases 5 et 6), le gateway n'effectue lui-même aucun appel LLM.
- Les agents restent pilotés par des instructions explicites : aucun test réel
  n'est déclenché sans message Telegram de l'utilisateur autorisé.

## Garde-fous vérifiés

- Aucune mission automatique.
- Aucun scheduler.
- Allowlist vérifiée sur chaque update.
- Aucun secret affiché ni journalisé, y compris lorsqu'un token est refusé par
  Telegram.
- Aucune écriture dans la base réelle `footballqa`.
- La base SQLite de pilotage reste locale.
- Une mission sensible reste bloquée tant qu'elle n'est pas approuvée.

---

## Test réel du bot — 10 novembre 2026

Environnement : PC personnel (`MAbdo`), bot `@Quaresma_QA_bot`, gateway lancé
avec `.venv\Scripts\python.exe -m app.telegram.gateway`, logs locaux dans
`logs/telegram-gateway.log` (ignoré par Git), stack `football-qa-test` saine
(`8002`/`5175`/`5434`), `REAL_AGENTS_ENABLED=true`.

### Pré-vérifications

| Contrôle | Résultat |
|---|---|
| Jeton chargé depuis `.env` | `True` (booléen seulement, valeur jamais affichée) |
| `TELEGRAM_ALLOWED_USER_ID` renseigné | `True` |
| Autre processus de polling | aucun → **aucun `409 Conflict`** Telegram |
| `getMe` | `200`, `is_bot: true`, `@Quaresma_QA_bot` |
| Démarrage | `Application started`, `getUpdates` `200` |
| `JobQueue` / scheduler | **aucun** (vérifié dans les logs et par test unitaire) |

### Déroulé validé

1. **`/start`** → texte identique à `START_TEXT` (rappel : aucune mission
   automatique).
2. **`/help`** → texte identique à `HELP_TEXT`.
3. **Texte libre** → mission réelle `8c568cce0ef4` créée puis exécutée :
   6/6 tâches `completed`, 21/21 sondes, 27/27 tests API, 11/11 scénarios UI,
   **0 anomalie**, durée 92 s. Rapport
   `reports/missions/8c568cce0ef4.md`.
4. **`/status 8c568cce0ef4`** → mission, statut, instruction, rapport, les
   6 tâches et le dernier événement `mission_completed`.
5. **`/missions`** → 5 missions, la plus récente en tête.
6. **Garde-fou d'approbation** → « Publie le rapport de la mission dans Jira »
   crée `8d7a1f40274d` avec `requires_approval=1`
   (`publication dans un outil externe`) et **0 tâche** exécutée.
7. **`/approve 8d7a1f40274d`** → événement `mission_approved`, 3 tâches
   (`qa_analyst`, `test_designer`, `qa_reporter`), mission `completed`.
8. **`/stop c5d08e7742e2`** puis `/approve` tardif → mission `cancelled`,
   événements `mission_cancel_requested` → `mission_cancelled`, **0 tâche**,
   approbation tardive ignorée.

### Vérifications en base SQLite (`workspace/missions.db`)

| Contrôle | Résultat |
|---|---|
| Missions / tâches / événements après test | 7 / 33 / 106 |
| Mission `8c568cce0ef4` | `completed`, 6 tâches, preuves présentes |
| Mission `8d7a1f40274d` | `created` (0 tâche) puis `completed` après `/approve` |
| Mission `c5d08e7742e2` | `cancelled`, 0 tâche |
| `PRAGMA integrity_check` après arrêt | `ok` |
| Base réelle `footballqa` | **non touchée** |

### Incident de sécurité trouvé et corrigé

Au premier lancement, `httpx` a journalisé l'URL complète de l'API Bot, qui
contient le jeton : le secret est apparu en clair dans le fichier de log local.
Correctif immédiat :

- gateway arrêté, log purgé puis recréé ;
- `SecretRedactionFilter` ajouté dans `app/telegram/gateway.py` et installé au
  démarrage sur le logger racine **et** ses handlers : toute occurrence du
  jeton est remplacée par `[redacted]`, y compris dans les logs d'`httpx` ;
- test `test_log_records_never_contain_the_token` ajouté ;
- `logs/` ignoré par Git.

Après relance, la vérification `TOKEN_IN_LOG = False` est passée. Aucune valeur
de secret n'apparaît dans ce rapport.

### Arrêt du gateway

Processus arrêté (le shell d'arrière-plan ne permet pas de délivrer `Ctrl+C`
au processus caché), puis vérifié :

- plus aucun processus `app.telegram.gateway` ;
- `getUpdates` répond `200` sans `409` → plus aucun polling résiduel ;
- `PRAGMA integrity_check` = `ok` (écritures SQLite déjà validées, une
  transaction par opération).

### Limite restante

Le refus d'un **compte non autorisé** n'a pas pu être rejoué en réel faute de
second compte Telegram disponible dans la session. Il reste couvert par
`tests/test_telegram_auth.py` (5 tests) et par le test de garde du gateway
(`test_unknown_user_is_denied_without_manager_access`,
`test_missing_user_is_denied`).

### Résultat

Bot Telegram **validé en réel** sur les commandes, la création et l'exécution
d'une mission réelle, l'approbation, l'annulation et l'absence de scheduler.
Suite du système : **72 tests réussis**.

### Ajout postérieur au test réel : retour d'attente

Le test réel a mis en évidence un défaut d'expérience : pendant l'exécution
d'une mission (jusqu'à plusieurs minutes), le bot restait muet et l'utilisateur
ne savait pas si son message avait été reçu. Correctif (version 0.6.6) :

- réponse immédiate `Mission <id> créée. ⏳ Exécution en cours…` (texte libre) ou
  `Mission <id> approuvée. ⏳ Exécution en cours…` (`/approve`) ;
- `send_chat_action(..., typing)` renvoyé toutes les 4 s pendant l'exécution
  (`TYPING_INTERVAL_SECONDS`), arrêté proprement à la fin ;
- réponse finale enrichie de la **durée réelle** (`Durée : N s`) ;
- un échec de l'indicateur est journalisé en debug et n'interrompt jamais la
  mission ;
- les missions en attente d'approbation ne reçoivent pas de message d'attente
  (elles ne s'exécutent pas).

Couverture : `test_typing_indicator_is_sent_during_execution`,
`test_typing_indicator_failure_does_not_break_the_mission`,
`test_waiting_message_is_not_sent_when_approval_is_required`, et assertions
d'ordre des réponses sur texte libre et `/approve`.

#### Validation en réel du retour d'attente

Le correctif a été rejoué sur le bot le 10 novembre 2026, mission
**`98943bcedbdd`** (« Analyse l'application et propose un plan de test ») :

| Contrôle | Résultat |
|---|---|
| Message d'attente | envoyé immédiatement (création à 13:53:48 UTC) |
| Indicateur d'activité | **21 `sendChatAction`** au total, espacés de ~4 s pendant les 83 s d'exécution |
| Réponse finale | envoyée à 13:55:11 UTC, avec statut, **durée** et chemin du rapport |
| Mission | `completed`, 3 tâches (`qa_analyst`, `test_designer`, `qa_reporter`) |
| Rapport | `reports/missions/98943bcedbdd.md` |
| Erreurs Telegram | 0 ; jeton toujours masqué dans les logs |

État de la base après la session : 8 missions / 36 tâches / 118 événements,
`PRAGMA integrity_check = ok`.
