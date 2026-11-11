# Phase 9 — Plan de durcissement

**Statut : plan rédigé, phase NON commencée.**
Date de rédaction : 11 novembre 2026.
Point de départ : `main` au commit `97b213e` (phase 8 fusionnée), **103 tests verts**.
Ce document est la spécification de travail de la phase 9. Il ne remplace pas
`PROJECT_CONTEXT.md` : il le complète pour l'exécution.

> Règle : la phase 9 ne démarre que sur demande explicite. Ce plan n'autorise
> ni mission réelle, ni scheduler, ni écriture dans la base cible.

---

## 1. Objectif

Rendre le système existant **sûr, résilient et exploitable**, sans ajouter de
fonctionnalité métier :

1. **Sécurité** : aucun secret dans les logs, rapports, artefacts ou réponses
   HTTP ; entrées validées ; chemins confinés ; surfaces réseau limitées.
2. **Robustesse** : comportement défini en cas de panne (LLM, API/UI, SQLite,
   processus interrompu), sans blocage silencieux ni perte de preuve.
3. **Qualité** : lint (et typage optionnel) dans la CI, versions cohérentes,
   dépendances maîtrisées.
4. **Documentation finale** : runbook d'exploitation, checklist sécurité,
   rapport de phase, cohérence des trois documents obligatoires.

### Hors périmètre

- Aucune nouvelle fonctionnalité visible (pas de nouveau dashboard, agent ou
  type de mission).
- Aucun service payant, aucun LLM supplémentaire, aucune dépendance payante.
- Aucun scheduler, aucune mission automatique, aucun test périodique.
- Aucun push direct sur `main`, aucune fusion automatique par le code.
- Aucune réécriture d'architecture : on durcit l'existant.

### Règles projet à respecter

- Budget **0 €**, dépendances gratuites uniquement.
- Tests **hors ligne**, sans clé, sans réseau (la CI peut installer des paquets,
  mais la suite ne doit appeler aucun service externe).
- Ne jamais afficher, journaliser ou envoyer un secret.
- Branche dédiée + PR + CI verte + fusion par l'agent.
- `README.md`, `PROJECT_CONTEXT.md` et `CHANGELOG.md` mis à jour à chaque PR.

---

## 2. Point de départ vérifié

| Élément | Valeur |
|---|---|
| Branche de référence | `main` |
| Commit | `97b213e` — phase 8 |
| Tests | **103 passed** (`python -m pytest`) |
| Python local | 3.12.10, `.venv` |
| CI | `.github/workflows/tests.yml`, `pytest` seul, Python 3.12 |
| Dépendances | `requirements.txt` épinglé (`==`) |
| Base de pilotage | SQLite local, `workspace/missions.db` |
| Bureau | `office/`, lecture seule, SSE local |
| Version `pyproject.toml` | `0.1.0` **(incohérente avec le CHANGELOG 0.8.0)** |

### Acquis à ne pas casser

Ces protections existent déjà et doivent rester couvertes par des tests :

- allowlist Telegram stricte (`app/telegram/auth.py`), message de refus neutre ;
- cibles API/UI limitées à `localhost:8002` / `localhost:5175`
  (`app/tools/api_probe.py`, `app/tools/api_suite.py`, `app/tools/ui_suite.py`) ;
- bureau écoute uniquement `127.0.0.1` / `localhost` / `::1`, identifiants de
  mission filtrés par regex, fichiers statiques confinés (`is_relative_to`),
  CSP et en-têtes de sécurité (`app/office/server.py`) ;
- rédaction des preuves API/UI/Allure (`app/tools/redaction.py`) ;
- Gemini : clé absente des erreurs, retries bornés, timeout
  (`app/llm/gemini.py`) ;
- DevOps : branche dédiée, mode préparation par défaut, jamais de fusion
  (`app/tools/devops.py`) ;
- `subprocess.run` avec listes d'arguments, sans shell, timeouts présents.

---

## 3. Audit initial — écarts à traiter

Priorités : **P0** indispensable, **P1** important, **P2** utile.

| ID | Constat | Preuve / fichier | Priorité |
|---|---|---|---|
| R1 | Les identifiants de mission ne sont validés qu'au niveau du serveur du bureau. `workspace.py` et `devops.py` construisent des chemins avec l'identifiant reçu (CLI, scripts), ce qui autorise une traversée locale. | `app/tools/workspace.py`, `app/tools/devops.py`, `scripts/*` | **P0** |
| R2 | `write_mission_text()` / `write_mission_json()` acceptent un chemin relatif non confiné : un appelant peut écrire hors du dossier de mission. | `app/tools/workspace.py` | **P0** |
| R3 | La rédaction n'est pas appliquée au point de sérialisation du bureau (`/api/state`, SSE) ni aux payloads d'événements : un secret injecté dans un résultat de tâche serait renvoyé tel quel. | `app/office/state.py`, `app/office/server.py` | **P0** |
| R4 | Aucun test de non-fuite avec un **secret sentinelle** dans les rapports Markdown/JSON, les fichiers Allure et les réponses du bureau. | `tests/` | **P0** |
| R5 | Le filtre `SecretRedactionFilter` couvre le logger racine et les handlers existants, mais pas un handler ajouté après l'installation ni un logger avec handler propre. | `app/telegram/gateway.py` | P1 |
| R6 | Le bureau utilise `ThreadingHTTPServer` sans limite de clients SSE ni timeout socket ; chaque événement reconstruit l'état complet (amplification locale possible). | `app/office/server.py` | P1 |
| R7 | SQLite n'active pas WAL ni `busy_timeout` explicite ; le verrou `RLock` est intra-processus seulement (gateway + bureau + scripts = processus séparés). | `app/store/sqlite_store.py` | P1 |
| R8 | Aucune politique de reprise pour une mission restée `running` après un arrêt brutal ; la reprise par checkpoint n'est pas testée. | `app/orchestrator/manager.py`, `app/orchestrator/graph.py` | P1 |
| R9 | `pyproject.toml` est en `0.1.0` alors que le CHANGELOG est en `0.8.0` ; aucun lint ni typage dans la CI. | `pyproject.toml`, `.github/workflows/tests.yml` | P1 |
| R10 | `_snippet()` (stderr Git) et les rapports DevOps ne passent pas par la rédaction ; une URL de remote contenant un identifiant pourrait fuiter. | `app/tools/devops.py` | P1 |
| R11 | Aucun test ne garantit l'absence de `shell=True`, d'arguments non listés ou de `--force` dans les commandes Git. | `tests/test_phase7_agents.py` | P2 |
| R12 | Les messages Telegram ne sont pas bornés avant persistance (le prompt LLM est tronqué à 30 000 caractères, mais l'instruction et les événements peuvent être volumineux). | `app/telegram/gateway.py`, `app/orchestrator/manager.py` | P2 |
| R13 | Pas de configuration de journalisation centralisée hors gateway ; pas de rotation des logs ; la CLI n'écrit pas de journal. | `app/telegram/gateway.py`, `app/cli.py` | P2 |
| R14 | Documentation d'exploitation incomplète : pas de runbook ni de checklist sécurité consolidée ; pas de rapport de phase 8. | `README.md`, `PROJECT_CONTEXT.md`, `reports/` | P1 |

> Ces constats sont issus d'une lecture ciblée, pas d'un audit exhaustif. La
> première tâche de la phase 9 est de les confirmer par un test qui échoue
> avant correction, puis de les corriger.

---

## 4. Travaux

### WP1 — Identifiants, chemins et secrets (P0)

**But** : une seule barrière de validation, utilisée partout.

1. Créer `app/security.py` (ou étendre `app/tools/redaction.py` si c'est plus
   simple) avec :
   - `MISSION_ID_PATTERN = ^[A-Za-z0-9_-]{1,64}$` ;
   - `validate_mission_id(value) -> str` (lève `ValueError`) ;
   - `ensure_within(base: Path, candidate: Path) -> Path` ;
   - `redact_structure(value, secrets)` pour les dict/list/str ;
   - éventuellement `validate_git_ref(value)` (refuse `-`, espaces, `..`).
2. Utiliser `validate_mission_id` dans :
   - `app/office/server.py` (remplacer la regex locale) ;
   - `app/tools/workspace.py` ;
   - `app/tools/devops.py` ;
   - `app/cli.py` et les scripts `scripts/run_*` ;
   - `app/office/state.py` avant de construire un chemin Allure.
3. Confiner `write_mission_text` / `write_mission_json` avec `ensure_within`.
4. Appliquer `redact_structure` avec les secrets connus (`gemini_api_key`,
   `telegram_bot_token`, mots de passe de test) :
   - dans `serialize_event()` et `build_office_state()` ;
   - dans les rapports Markdown/JSON et les fichiers Allure ;
   - dans `_snippet()` et le rapport DevOps.
5. **Tests** (`tests/test_security.py`) :
   - identifiants refusés : `""`, `../x`, `..\\x`, `/abs`, `a/b`, 65 caractères ;
   - `write_mission_text` refuse `../../evasion.txt` ;
   - un secret sentinelle dans `task.result`, `event.payload`, un rapport et un
     résultat Allure n'apparaît **jamais** dans `/api/state`, le SSE, le
     Markdown ou le JSON ;
   - les identifiants valides existants continuent de fonctionner.

**Critères d'acceptation** : aucun chemin hors workspace, aucun secret
sentinelle dans une sortie, 103 tests existants toujours verts.

---

### WP2 — Surface HTTP et flux SSE (P1)

**But** : garder le bureau local, sobre et non bloquant.

1. `app/office/server.py` :
   - limite explicite du nombre de clients SSE simultanés (valeur constante,
     réponse `503` au-delà) ;
   - `timeout` de socket / écriture pour éviter un client lent qui bloque un
     thread ;
   - reconstruire l'état **une fois par lot d'événements**, pas une fois par
     événement ;
   - vérifier que toutes les réponses (y compris erreurs) portent les en-têtes
     de sécurité ;
   - documenter `HEAD`/méthodes non supportées (réponse claire, pas de trace).
2. Tests :
   - N clients SSE acceptés, N+1 refusé ;
   - en-têtes présents sur `/`, `/api/state`, erreurs 400/404/503 ;
   - déconnexion brutale d'un client sans exception non gérée ;
   - un lot de plusieurs événements ne provoque qu'une reconstruction d'état
     (mesure par compteur injecté ou mock).
3. Ne pas ajouter de dépendance : tout doit rester en bibliothèque standard.

**Critères d'acceptation** : le bureau reste réactif avec plusieurs onglets,
ne fuit pas de thread et refuse proprement au-delà de la limite.

---

### WP3 — Persistance, concurrence et reprise (P1)

**But** : aucune perte silencieuse, aucune base verrouillée sans message clair.

1. `app/store/sqlite_store.py` :
   - activer `PRAGMA journal_mode=WAL`, `busy_timeout` (ex. 5 000 ms),
     `synchronous=NORMAL`, `foreign_keys=ON` à la connexion ;
   - retry borné sur `sqlite3.OperationalError` de type `database is locked` ;
   - mode lecture seule pour le bureau si c'est simple (sinon documenter
     pourquoi le store partagé reste acceptable) ;
   - erreur explicite et message utilisateur si la base est corrompue.
2. `app/orchestrator/manager.py` :
   - documenter et tester la reprise d'une mission `running` interrompue :
     `run_mission()` reprend via le checkpoint LangGraph sans dupliquer les
     tâches ;
   - s'assurer que `close()` est toujours appelé (contexte ou `try/finally`
     dans les scripts) ;
   - ajouter une commande **explicite et en lecture seule** `python -m app.cli
     doctor` qui liste missions bloquées, tâches orphelines et incohérences,
     sans rien réparer automatiquement.
3. Tests :
   - deux instances de store en threads, lecture pendant écriture ;
   - simulation de `database is locked` puis succès après retry ;
   - base corrompue → message clair, pas de stack brute ;
   - mission `running` reprise → pas de doublon de tâches ni d'événements ;
   - `doctor` ne modifie rien (comparaison avant/après).

**Critères d'acceptation** : concurrence lecture/écriture stable, reprise
idempotente, diagnostic explicite sans scheduler.

---

### WP4 — Garde-fous DevOps et sous-processus (P1)

**But** : prouver que l'agent ne peut pas pousser sur `main`, forcer un push
ou fusionner.

1. Tests dans `tests/test_phase7_agents.py` (ou nouveau fichier dédié) :
   - aucune commande ne contient `push` vers `main` ni `--force` ;
   - `publish=False` ne produit aucune mutation Git ;
   - `publish=True` sans `DEVOPS_PUBLISH_ENABLED` reste bloqué ;
   - arbre Git non propre → blocage, aucune copie ;
   - `merged` reste toujours `False` ;
   - les commandes sont des listes, jamais des chaînes avec `shell=True` ;
   - un remote contenant un secret sentinelle est expurgé du rapport et du
     `blocked_reason`.
2. Valider `devops_remote`, `devops_base_branch` et le nom de branche généré
   (refus des valeurs commençant par `-`, des espaces et de `..`).
3. Vérifier les timeouts des suites API/UI et de `git` (aucun appel sans
   borne).

**Critères d'acceptation** : les garde-fous sont testés, pas seulement
documentés.

---

### WP5 — Qualité, CI et versions (P1)

**But** : empêcher les régressions de style et de typage sans alourdir.

1. Ajouter `ruff` (gratuit) comme outil de développement :
   - configuration minimale dans `pyproject.toml` (ligne 88, imports, bugs
     évidents) ;
   - étape `ruff check .` dans `.github/workflows/tests.yml` avant `pytest` ;
   - corriger les violations existantes (ou les ignorer explicitement avec
     justification).
2. Typage **optionnel** : si le coût reste raisonnable, ajouter `mypy` en mode
   progressif sur `app/` avec une liste d'exceptions ; sinon documenter la
   décision et ne pas l'ajouter.
3. Aligner la version : `pyproject.toml` → `0.9.0` (ou la version décidée),
   cohérente avec `CHANGELOG.md`.
4. Ajouter un test de cohérence documentaire simple : la dernière version du
   CHANGELOG et celle de `pyproject.toml` ne divergent pas.
5. Ne pas ajouter de dépendance runtime ; `ruff`/`mypy` restent des outils de
   développement.

**Critères d'acceptation** : CI = lint + tests, verte, sans réseau pendant la
suite ; aucune dépendance payante.

---

### WP6 — Documentation finale et exploitation (P1)

**But** : une personne externe peut installer, lancer, diagnostiquer et
comprendre les garanties.

1. `reports/phase-9-hardening.md` : rapport final (constats, correctifs,
   tests ajoutés, preuves, limites restantes).
2. `README.md` :
   - section « Sécurité et garanties » consolidée ;
   - procédure de dépannage rapide ;
   - version et nombre de tests à jour.
3. `PROJECT_CONTEXT.md` :
   - phase 9 terminée, décisions prises (WAL, limites SSE, validation
     centralisée, ruff) ;
   - commandes `doctor`, vérifications, pièges connus.
4. `CHANGELOG.md` : entrée `0.9.0` datée.
5. Checklist sécurité finale, par exemple dans le rapport :
   - secrets absents des logs/rapports/artefacts/HTTP ;
   - cibles réseau limitées ;
   - chemins confinés ;
   - CI verte ;
   - aucune mission automatique ;
   - aucune fusion automatique.
6. Vérifier la cohérence des liens, commandes et numéros de version dans les
   trois documents.

**Critères d'acceptation** : un nouvel arrivant peut reproduire une mission de
test hors ligne et ouvrir le bureau sans lire le code.

---

## 5. Ordre d'exécution recommandé

| Jalon | Contenu | PR suggérée |
|---|---|---|
| J0 | Baseline : tests, `ruff` en observation, confirmation des constats R1–R4 par des tests rouges | `chore/phase9-baseline` |
| J1 | WP1 + WP4 : sécurité des identifiants, chemins, secrets, garde-fous Git | `security/phase9-boundaries` |
| J2 | WP2 + WP3 : bureau et persistance | `robustness/phase9-runtime` |
| J3 | WP5 : lint/CI/version | `chore/phase9-quality` |
| J4 | WP6 : rapport et documentation finale | `docs/phase9-final` |

Chaque PR : branche dédiée, CI verte, fusion par l'agent, documentation mise à
jour. Ne pas tout regrouper dans une seule PR géante : les correctifs de
sécurité doivent être relisibles isolément.

---

## 6. Plan de tests

Fichiers à créer ou compléter :

- `tests/test_security.py` : identifiants, chemins, rédaction, sentinelle.
- `tests/test_store_robustness.py` : WAL, concurrence, verrou, corruption.
- `tests/test_manager_recovery.py` : reprise de mission `running`, `doctor`.
- `tests/test_office_security.py` : limites SSE, en-têtes, rédaction HTTP.
- `tests/test_phase7_agents.py` : garde-fous Git renforcés.
- `tests/test_docs_consistency.py` : versions/phase cohérentes.

Objectif indicatif : **120 à 140 tests**, tous hors ligne, sans clé, sans
réseau. Le nombre exact importe moins que la couverture des risques ci-dessus.

---

## 7. Definition of Done de la phase 9

- [ ] Les constats R1 à R14 sont confirmés ou explicitement écartés avec
      justification.
- [ ] Aucun secret sentinelle ne fuit dans les logs, rapports, artefacts
      Allure, `/api/state` ou le SSE.
- [ ] Tous les identifiants et chemins sont validés à une barrière unique.
- [ ] Le bureau refuse proprement au-delà de sa limite SSE et ne bloque pas.
- [ ] SQLite fonctionne en WAL avec `busy_timeout` et retry borné.
- [ ] Une mission `running` interrompue peut être reprise sans doublon.
- [ ] Les garde-fous Git (pas de `main`, pas de force, pas de fusion) sont
      testés.
- [ ] `ruff` passe et la CI exécute lint + tests.
- [ ] Les versions `pyproject.toml` / CHANGELOG sont alignées.
- [ ] `README.md`, `PROJECT_CONTEXT.md`, `CHANGELOG.md` et
      `reports/phase-9-hardening.md` sont à jour.
- [ ] Aucune dépendance payante, aucun scheduler, aucune mission automatique.
- [ ] CI verte et PR fusionnée.

---

## 8. Risques et pièges

- **Ne pas casser la compatibilité des bases existantes** : les PRAGMA et les
  retries ne doivent pas migrer destructivement. Tester sur une copie.
- **WAL + LangGraph** : vérifier que le checkpoint SQLite supporte WAL et les
  accès concurrents ; sinon isoler la base de checkpoint.
- **Rédaction trop agressive** : ne pas masquer des informations utiles au
  diagnostic (préférer `[redacted]` ciblé aux secrets connus et aux motifs).
- **Limite SSE** : choisir une valeur assez haute pour l'usage local (8–16) et
  la documenter.
- **Ruff** : ne pas introduire des centaines de corrections cosmétiques dans
  une PR de sécurité ; séparer.
- **CI hors ligne** : `ruff` s'installe via pip mais la suite de tests ne doit
  faire aucun appel réseau.
- **Windows** : les scripts utilisent des chemins Windows ; garder les tests
  portables et ne pas dépendre de la casse.
- **Secrets** : ne jamais utiliser un vrai secret dans un test ; uniquement
  des valeurs sentinelles factices.

---

## 9. Commandes de vérification

```powershell
# Baseline
.venv\Scripts\python.exe -m pytest -q

# Après ajout du lint
.venv\Scripts\python.exe -m ruff check .

# Diagnostic lecture seule (à créer en WP3)
.venv\Scripts\python.exe -m app.cli doctor

# Bureau local
.venv\Scripts\python.exe scripts\run_office.py --mission-id <mission_id>
```

Attendu : suite verte, aucune erreur de lint, `doctor` ne modifie rien,
bureau accessible uniquement en local.

---

## 10. Prompt de démarrage pour la nouvelle session

> Lis d'abord `PROJECT_CONTEXT.md` puis `reports/phase-9-plan.md`.
> La phase 8 est terminée sur `main` (`97b213e`, 103 tests verts). La phase 9
> n'est **pas** commencée : le plan est la spécification à exécuter.
>
> Exécute la phase 9 en suivant l'ordre J0 → J4 du plan, une PR par jalon :
> `chore/phase9-baseline`, `security/phase9-boundaries`,
> `robustness/phase9-runtime`, `chore/phase9-quality`, `docs/phase9-final`.
> Pour chaque PR : branche dédiée, tests hors ligne sans clé, CI verte, fusion
> par l'agent, mise à jour de `README.md`, `PROJECT_CONTEXT.md` et
> `CHANGELOG.md`.
>
> Commence par J0 : confirme la baseline (103 tests), puis écris les tests
> rouges des constats R1 à R4 avant toute correction. Ne crée aucune mission
> réelle, n'ajoute aucun scheduler, ne pousse jamais sur `main` et n'affiche
> jamais de secret. Budget 0 €, aucune dépendance payante.
>
> Termine par `reports/phase-9-hardening.md` et la checklist de la section 7
> du plan (Definition of Done).

---

## 11. Ce qui est volontairement laissé à la nouvelle session

- Le choix final des seuils (limite SSE, `busy_timeout`, retries).
- L'ajout ou non de `mypy` selon le coût réel.
- La structure exacte de `app/security.py` (nouveau module ou extension de
  `redaction.py`).
- Le découpage fin des PR, tant que les jalons et les critères d'acceptation
  sont respectés.

Toute décision prise devra être consignée dans `PROJECT_CONTEXT.md` et
`CHANGELOG.md`.
