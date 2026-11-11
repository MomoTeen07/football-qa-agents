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

### En cours — Phase 9 : durcissement

#### J0 — baseline (11 novembre 2026)

##### Ajouté

- **Tests rouges R1 à R4** (`tests/test_security.py`, 8 tests) : traversée
  d'identifiant de mission (`workspace`, DevOps), écriture hors dossier de
  mission, rédaction absente de `build_office_state` / `serialize_event`, fuite
  d'un secret sentinelle dans les rapports Markdown/JSON et les fichiers Allure.
  Ils sont marqués `xfail(strict=True)` jusqu'à leur correction au jalon J1.

##### Vérifié

- Baseline `main` `0179751` : **103 passed** avant tout ajout.
- Suite après ajout : **103 passed, 8 xfailed** (aucune régression).

### À venir

- **Phase 9** — jalons J1 (sécurité des identifiants, chemins, secrets et
  garde-fous Git), J2 (bureau et persistance), J3 (lint/CI/version), J4
  (documentation finale).

### Ajouté

- **Plan détaillé de la phase 9** (`reports/phase-9-plan.md`, 11 novembre
  2026) : audit initial des écarts (identifiants/chemins, secrets, SSE,
  SQLite, reprise, garde-fous Git, CI, documentation), six lots de travail
  priorisés, jalons J0 à J4, plan de tests et Definition of Done. **La phase 9
  n'est pas commencée** : ce document sert de spécification à la session
  suivante.

### Modifié

- **Politique de fusion Git** (10 novembre 2026) : la validation humaine des
  pull requests n'est plus requise. L'agent ouvre la PR, vérifie les tests et
  la fusionne lui-même. Le principe « branche + PR, pas de push direct sur
  `main` » est conservé. Documenté dans `README.md` et `PROJECT_CONTEXT.md`.

---

## [0.8.0] — 2026-11-11 — Phase 8 : bureau virtuel 2D

### Ajouté

- **Bureau virtuel isométrique** (`office/`) : frontend statique sans build
  (HTML/CSS/JS natifs) représentant les 8 agents réels dans un open space
  pixel art, avec six départements, postes de travail, décor, panneau latéral
  et légende des statuts.
- **Serveur local en lecture seule** (`app/office/server.py`,
  `scripts/run_office.py`) : `http.server` de la bibliothèque standard, écoute
  strictement sur la boucle locale, sert le frontend et expose
  `/api/state`, `/api/missions` et `/events` (SSE). Aucune mission n'est créée
  ni lancée par le bureau.
- **Flux SSE réel** (`app/office/stream.py`) : combine l'abonnement à
  l'`EventBus` en mémoire et la relecture du journal SQLite, avec
  déduplication par identifiant d'événement. Fonctionne donc aussi quand le
  gateway Telegram tourne dans un autre processus.
- **Cartographie réelle de l'état** (`app/office/state.py`) : statuts
  d'agents, mission courante, progression, preuves, résultats Allure,
  événements et activité récente sont dérivés des missions, tâches et
  événements persistés. Aucune donnée simulée.
- **Passations réelles** : un personnage ne se déplace que lorsqu'une tâche
  dépend d'une tâche terminée portée par un autre agent (`depends_on`), puis
  revient à son poste.
- **Fiche agent** : rôle, département, statut, tâche courante, liste des
  tâches, dernier résultat et historique, ouverte au clic sur un personnage ou
  dans la liste « Agents ».
- **Flux temps réel sobre** : bulles dédupliquées par agent et plafonnées à
  quatre, file d'animations limitée, veille de mission toutes les 5 s via
  `setTimeout` quand le bureau est ouvert avant la première mission.
- **Tests** (`tests/test_office.py`) : catalogue, cartographie des statuts,
  passations dérivées des dépendances, synthèse Allure, flux mémoire/SQLite,
  endpoints HTTP, SSE, refus d'une interface non locale, traversée de chemins,
  absence de `Math.random`/`setInterval`/URL externe dans le frontend et
  présence de `key` dans les événements de tâche.

### Modifié

- **`app/orchestrator/graph.py`** : les événements `task_started`,
  `task_completed`, `task_failed` et `task_blocked` incluent désormais la clé
  de tâche (`key`), ce qui permet au bureau d'associer un événement à la bonne
  tâche sans heuristique.
- **`.gitignore`** : les bases et rapports de démonstration
  `workspace/office-*/` ainsi que les aperçus locaux `preview-*` sont ignorés.
- **Documentation** : `README.md` et `PROJECT_CONTEXT.md` décrivent le
  lancement, les garanties « événements réels uniquement » et l'état de la
  phase 8. Suite du système : **103 tests passent**.

### Pourquoi

Le bureau devait représenter la mission sans jamais inventer d'activité. Toute
animation est donc dérivée d'un événement enregistré ou d'une dépendance
réelle entre tâches ; sans mission, les huit agents restent disponibles et
silencieux.

---

## [0.7.0] — 2026-11-11 — Phase 7 : agent DevOps et reporting Allure

### Ajouté

- **Agent 6 DevOps réel** (`app/agents/phase7.py`, `app/tools/devops.py`) :
  recense les suites générées d'une mission, crée une branche dédiée
  `qa/promotion-<mission>`, y commit `test_api_suite.py` et
  `run_ui_checks.py` accompagnés d'un manifeste `promotion.json`, pousse la
  branche puis ouvre une pull request via `gh pr create`.
- **Mode préparation par défaut** : sans `DEVOPS_PUBLISH_ENABLED=true`, aucune
  copie, aucun commit, aucun push et aucune PR. Le statut est `planned` avec la
  branche et les fichiers calculés.
- **Garde-fous DevOps** : refus d'un arbre de travail non propre, d'une branche
  locale déjà existante, d'un dépôt absent ; échec de `fetch`, `push` ou `gh`
  rapporté en statut `blocked` sans anomalie applicative. Jamais de `--force`,
  jamais de push sur `main`, jamais de fusion automatique.
- **Agent 7 reporter enrichi** : synthèse globale des sources réelles, rapport
  Markdown, synthèse JSON (`reports/missions/<mission>.json`) et résultats
  **Allure 2** standards (`reports/allure-results/<mission>/`).
- **`app/tools/allure_report.py`** : génération Allure 2 en Python pur, sans
  dépendance supplémentaire — résultats `*-result.json`, attaches texte et
  captures Playwright, `environment.properties`, `executor.json`,
  `allure-summary.json` et `allure-report.md`. Identifiants déterministes,
  secrets expurgés, aucun résultat inventé sans preuve réelle.
- **`scripts/run_phase7_mission.py`** : régénère explicitement le rapport d'une
  mission existante et prépare la promotion DevOps ; `--publish` sert de
  confirmation explicite.
- **Configuration** : `ALLURE_RESULTS_DIR`, `DEVOPS_PUBLISH_ENABLED`,
  `DEVOPS_REMOTE`, `DEVOPS_BASE_BRANCH`, `DEVOPS_TIMEOUT_SECONDS`
  (documentées dans `.env.example`).

### Modifié

- **Planificateur** : toute instruction Git/PR rejoint les groupes soumis à
  approbation ; le mot-clé `ci` est affiné en ` ci ` / `ci/` pour éviter les
  faux positifs.
- **Graphe** : les preuves du reporter sont journalisées dans la tâche et dans
  l'événement `report_ready`.
- **`app/agents/stubs.py`** : ne définit plus d'agent, ré-exporte seulement
  `DevOpsAgent` et `QAReporterAgent` depuis `app/agents/phase7.py`.
- **Tests** : **90 tests réussis** (72 avant), dont 6 pour Allure et 12 pour
  les agents 6/7, le reporter enrichi et l'approbation Git/PR.
- **Documentation** : `ALLURE_RESULTS_DIR`, `DEVOPS_REPO_DIR` et
  `DEVOPS_TIMEOUT_SECONDS` documentés dans `.env.example`, `README.md` et
  `PROJECT_CONTEXT.md` ; lien vers la **PR #11** ajouté aux rapports.

### Validé en réel

- Mission de référence `7e30889c18cd` régénérée le 11 novembre 2026 :
  **59 résultats Allure** (21 sondes + 27 API + 11 UI), **59 réussis**,
  0 échec, 0 anomalie.
- Rendu HTML généré sans erreur par la **CLI Allure 2.46.2** (outil gratuit et
  optionnel) depuis `reports/allure-results/7e30889c18cd`.
- Promotion DevOps en mode préparation : `DEVOPS_STATUS=planned`, branche
  `qa/promotion-7e30889c18cd`, 3 fichiers, aucune opération distante.

### Limites connues

- La **publication Git réelle** (branche distante + PR) n'a pas été exécutée
  pendant la validation : elle exige `DEVOPS_PUBLISH_ENABLED=true` et
  `--publish`. Le code est couvert par 12 tests avec un exécuteur Git simulé.
- La CLI Allure reste optionnelle : seuls les fichiers JSON standard sont
  produits par le projet.

---

## [0.6.6] — 2026-11-10 — Retour d'attente pendant l'exécution d'une mission

### Ajouté

- **Message d'attente immédiat** : sur texte libre (et sur `/approve`), le
  gateway répond tout de suite `Mission <id> créée. ⏳ Exécution en cours…`
  avant de lancer les agents, puis envoie le résultat dans le même fil.
  Auparavant, le bot restait muet plusieurs minutes et l'utilisateur ne savait
  pas si son message avait été reçu.
- **Indicateur d'activité Telegram** : `send_chat_action(..., typing)` est
  renvoyé toutes les 4 s pendant toute la durée de l'exécution
  (`TYPING_INTERVAL_SECONDS`), puis arrêté proprement. Un échec de cet
  indicateur n'interrompt jamais la mission.
- **Durée réelle dans la réponse finale** (`Durée : N s`).

### Modifié

- `_run_mission_with_feedback` encapsule l'exécution et la boucle d'indicateur ;
  l'utilisateur est informé avant, pendant et après le traitement.
- Suite complète : **72 tests réussis** (69 avant), dont 3 nouveaux tests
  (message d'attente avant exécution, indicateur d'activité, tolérance à un
  échec de l'indicateur) et une assertion renforcée sur `/approve`.

### Validé en réel

- Mission `98943bcedbdd` (« Analyse l'application et propose un plan de test »)
  exécutée depuis Telegram en 83 s : message d'attente immédiat, **21
  `sendChatAction`** espacés d'environ 4 s, réponse finale avec durée, statut
  `completed`, 3 tâches, 0 erreur Telegram.

---

## [0.6.5] — 2026-11-10 — Test réel du bot Telegram

### Ajouté

- **Validation réelle du gateway Telegram** sur le PC personnel avec
  `@Quaresma_QA_bot` (`TELEGRAM_BOT_TOKEN` renseigné, allowlist active,
  `REAL_AGENTS_ENABLED=true`). Aucun autre processus ne faisait de polling :
  démarrage sans `409 Conflict`.
- Commandes validées en réel : `/start`, `/help`, texte libre, `/status`,
  `/missions`, `/approve`, `/stop`.
- **Mission réelle créée et exécutée depuis Telegram** : `8c568cce0ef4`,
  6/6 tâches `completed`, 21/21 sondes API, 27/27 tests pytest API,
  11/11 scénarios Playwright, **0 anomalie**, durée 92 s.
- **Garde-fou d'approbation validé** : la mission `8d7a1f40274d`
  (« Publie le rapport de la mission dans Jira ») reste à l'état `created`
  avec 0 tâche jusqu'à `/approve`, puis s'exécute.
- **Annulation validée** : `/stop c5d08e7742e2` puis `/approve` tardif
  laissent la mission en `cancelled` (3 événements, 0 tâche) — une approbation
  tardive ne relance pas une mission annulée.
- **Filtre de rédaction des secrets** (`SecretRedactionFilter` dans
  `app/telegram/gateway.py`) installé au démarrage : le jeton Telegram est
  remplacé par `[redacted]` dans **tous** les logs, y compris ceux d'`httpx`.
- Test `test_log_records_never_contain_the_token` : vérifie qu'un log contenant
  le jeton ne le laisse jamais apparaître.
- `logs/` ajouté au `.gitignore` (journaux locaux du gateway).

### Corrigé

- **Fuite du jeton dans les logs** : au premier lancement réel, `httpx`
  journalisait l'URL complète `https://api.telegram.org/bot<token>/getMe`, donc
  le secret apparaissait en clair dans le fichier de log. Le log a été purgé et
  le filtre de rédaction empêche toute récidive. Aucune valeur de jeton n'est
  documentée, journalisée ou publiée.

### Modifié

- Suite complète : **69 tests réussis** (68 avant).
- `reports/phase-4-telegram.md` : ajout de la section de validation réelle.

### Limites connues

- Le test d'un **compte Telegram non autorisé** (message refusé
  « Accès refusé. ») n'a pas été exécuté en réel faute de second compte
  disponible pendant la session ; il est couvert par les 5 tests unitaires de
  `tests/test_telegram_auth.py` et par le test de garde du gateway. À rejouer
  dès qu'un second compte est disponible.
- `python-telegram-bot` traite les updates séquentiellement : pendant une
  mission longue, les commandes suivantes attendent la fin de l'exécution.
  Comportement attendu (pas de `concurrent_updates`), non corrigé en phase 4.

---

## [0.6.4] — 2026-11-10 — CI GitHub Actions et reprise sur erreurs Gemini

### Ajouté

- **CI GitHub Actions** (`.github/workflows/tests.yml`) : la suite pytest
  s'exécute sur chaque pull request et sur chaque push vers `main`
  (Python 3.12, dépendances de `requirements.txt`, aucune clé requise).
  Puisque les PR sont désormais fusionnées par l'agent, ce contrôle remplace
  la relecture humaine comme garde-fou.
- **Reprise sur erreurs transitoires Gemini** (`app/llm/gemini.py`) :
  les réponses `429` et `5xx` sont retentées avec un backoff exponentiel borné
  (3 tentatives max, 1 s puis 2 s, plafond 8 s). Les erreurs réseau et les
  `4xx` définitifs échouent immédiatement. Le repli déterministe reste actif
  si toutes les tentatives échouent.

### Modifié

- Tests du client Gemini : reprise sur `429` puis succès, abandon après
  `MAX_ATTEMPTS` sans fuite de clé, absence de reprise sur `400`.
- Suite complète : **68 tests réussis** (65 avant).

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
- Projet cible copié vers `C:\Users\MAbdo\Desktop\Football-Agent\football-qa`
  (chemin attendu par le compose de test).

### Pull request

- **PR #4** : <https://github.com/MomoTeen07/football-qa-agents/pull/4>
  (correctifs et documentation).

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
