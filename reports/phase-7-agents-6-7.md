# Phase 7 — Agents 6 et 7 (DevOps et reporting Allure)

Date : 11 novembre 2026

## Objectif

Remplacer les deux derniers stubs par des agents réels, sans jamais inventer de
résultat ni d'anomalie :

1. **DevOps** — promouvoir les suites générées sur une branche dédiée et ouvrir
   une pull request, sans jamais pousser sur `main`.
2. **QA Reporter** — produire un rapport enrichi : Markdown, synthèse JSON et
   résultats **Allure 2** standards, à partir des preuves réelles des phases 5
   et 6.

## État

- Code des agents 6 et 7 : **présent et câblé** dans le Manager, le graphe et
  le planificateur.
- Tests hors ligne : **18 nouveaux tests** (6 Allure + 12 DevOps/reporter),
  suite complète à **90 tests**.
- Validation réelle : **faite le 11 novembre 2026** sur la mission de
  référence `7e30889c18cd`.
- Aucune clé n'est nécessaire pour les tests hors ligne.
- Aucune dépendance payante : Allure 2 est écrit en Python pur, la CLI Allure
  n'est qu'un rendu HTML optionnel et gratuit.

## Composants

| Fichier | Rôle |
|---|---|
| `app/agents/phase7.py` | Agents `devops` et `qa_reporter`, avec repli déterministe. |
| `app/tools/devops.py` | Promotion Git sécurisée : branche, copie des suites, commit, push, PR. |
| `app/tools/allure_report.py` | Résultats Allure 2, attaches, captures, synthèse JSON et Markdown. |
| `app/agents/stubs.py` | Ré-exports de compatibilité, plus aucun agent défini ici. |
| `app/config.py` | `allure_results_dir`, `devops_publish_enabled`, `devops_repo_dir`, `devops_remote`, `devops_base_branch`, `devops_timeout_seconds`. |
| `app/orchestrator/planner.py` | Instructions Git/PR soumises à approbation, mot-clé `ci` affiné. |
| `app/orchestrator/graph.py` | Preuves du reporter dans la tâche et l'événement `report_ready`. |
| `scripts/run_phase7_mission.py` | Régénération du rapport et promotion DevOps, explicite uniquement. |
| `tests/test_allure_report.py` | 6 tests des résultats Allure 2 et des synthèses. |
| `tests/test_phase7_agents.py` | 12 tests DevOps, reporter enrichi et approbation. |

## Comportement de l'agent DevOps

### Mode préparation (par défaut)

`DEVOPS_PUBLISH_ENABLED=false` ⇒ statut `planned` :

- vérifie que le dossier est un dépôt Git ;
- calcule la branche `qa/promotion-<mission>` et les fichiers à promouvoir ;
- **n'exécute aucune commande Git mutante** : pas de copie, pas de `switch`,
  pas de `add`, pas de `commit`, pas de `push`, pas de `gh pr create`.

### Mode publication (opt-in)

`DEVOPS_PUBLISH_ENABLED=true` **et** confirmation `--publish` :

1. vérifie que l'arbre de travail est propre ;
2. refuse une branche locale déjà existante ;
3. `git fetch <remote> <base>` puis
   `git switch -c qa/promotion-<mission> <remote>/<base>` ;
4. copie `test_api_suite.py` et `run_ui_checks.py` dans
   `tests/generated/<mission>/`, avec un manifeste `promotion.json` ;
5. `git add`, `git commit`, `git push -u <remote> <branche>` ;
6. `gh pr create --base main --head qa/promotion-<mission>`.

### Garde-fous

- Jamais de push direct sur `main`, jamais de `--force`, jamais de fusion.
- Arbre non propre, branche existante, dépôt absent, échec `fetch`/`push`/`gh`
  ⇒ statut `blocked` avec raison explicite, **sans anomalie applicative**.
- Un échec de push conserve la branche locale et n'ouvre aucune PR.
- Un échec de PR conserve la branche poussée et le commit, sans masquer
  l'erreur.
- Toute instruction Git/PR est classée sensible par le planificateur et exige
  une approbation explicite.

## Comportement du reporter

Le reporter agrège :

- `api/probe-results.json` (phase 5) ;
- `api-automation/api-automation-results.json` (phase 6) ;
- `ui-automation/ui-automation-results.json` (phase 6).

Il produit :

- un rapport Markdown avec synthèse globale, statut par source, détail des
  tâches et anomalies réellement présentes ;
- `reports/missions/<mission>.json` : synthèse machine (sources, anomalies,
  totaux Allure, chemins) ;
- `reports/allure-results/<mission>/` :
  - un fichier `*-result.json` par vérification réelle,
  - les attaches texte et les captures Playwright,
  - `environment.properties`, `executor.json`, `allure-summary.json`,
  - `allure-report.md`.

Règles :

- statut `blocked` ⇒ résultat Allure `skipped`, **aucune anomalie** ;
- aucune preuve réelle ⇒ aucun résultat Allure n'est écrit ;
- identifiants `uuid5` déterministes ⇒ une régénération ne crée pas de doublon
  et supprime les résultats périmés ;
- messages, traces et attaches passent par l'expurgation des secrets connus ;
- aucune anomalie inventée.

## Validation hors ligne

```powershell
.venv\Scripts\python.exe -m pytest
# 90 passed
```

Les tests utilisent un exécuteur Git simulé et des payloads de preuve injectés :
aucun appel réseau, aucune stack cible, aucune clé, aucune opération Git réelle.

## Validation réelle — 11 novembre 2026

Machine : PC personnel (`MAbdo`), mission de référence `7e30889c18cd`
(21 sondes, 27 tests API, 11 scénarios UI).

```powershell
.venv\Scripts\python.exe scripts\run_phase7_mission.py --mission-id 7e30889c18cd
```

### Reporter et Allure

| Vérification | Résultat |
|---|---|
| Résultats Allure 2 générés | **59** (21 sondes + 27 API + 11 UI) |
| Réussis | 59 |
| Échecs / cassés / ignorés | 0 / 0 / 0 |
| Anomalies | 0 |
| Synthèse JSON | `reports/missions/7e30889c18cd.json` |
| Rapport Markdown | `reports/missions/7e30889c18cd.md` |
| Résultats Allure | `reports/allure-results/7e30889c18cd/` |

Chaque résultat contient `uuid`, `historyId`, `fullName`, `status`,
`statusDetails`, `stage`, `start`/`stop`, `labels`, `links` et `attachments`.
Les libellés portent la mission, la suite, le framework et la langue.

### Compatibilité CLI Allure

La **CLI Allure 2.46.2** (gratuite) a été téléchargée et exécutée sur les
résultats produits :

```powershell
allure generate reports\allure-results\7e30889c18cd -o <dossier-html> --clean
# Report successfully generated
# EXIT=0 ; index.html présent
```

Aucune erreur de parsing : le format est bien celui d'Allure 2. La CLI reste
optionnelle ; le projet ne dépend que des fichiers JSON standards.

### DevOps

| Vérification | Résultat |
|---|---|
| Statut | `planned` |
| Branche préparée | `qa/promotion-7e30889c18cd` |
| Fichiers à promouvoir | 3 (2 suites + manifeste) |
| Commit / PR | aucun (mode préparation) |
| Opération distante | aucune |

## Pull request

La phase 7 est proposée dans une PR dédiée depuis `main` :

- branche source : `feat/phase7-devops-allure`
- branche cible : `main`
- aucune fusion automatique avant vérification de la CI (`pytest`, sans clé) ;
- aucun push direct sur `main`.

## Limites connues

- La **publication Git réelle** de bout en bout (branche distante, PR ouverte)
  n'a pas été exécutée pendant cette session : elle exige
  `DEVOPS_PUBLISH_ENABLED=true` et `--publish`. Le chemin complet est couvert
  par 12 tests avec un exécuteur Git simulé (succès, arbre non propre, branche
  existante, échec de push, échec de PR).
- La CLI Allure n'est pas une dépendance du projet ; sans elle, les résultats
  JSON et les synthèses Markdown/JSON restent complets.
- Les rapports et preuves de mission restent **locaux** et ignorés par Git.
- Le test réel d'un compte Telegram non autorisé reste à rejouer avec un second
  compte (hérité de la phase 4).
