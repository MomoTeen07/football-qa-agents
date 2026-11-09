# Phase 3 — Socle du Manager QA

Date : 9 novembre 2026

## Composants créés

- Projet Python `football-qa-agents`.
- Environnement virtuel `.venv`.
- LangGraph 1.2.20.
- Stockage SQLite des missions, tâches et événements.
- Journal d'événements réel (`EventBus`).
- Manager QA déterministe.
- Sept agents de planification.
- CLI de gestion des missions.
- Tests automatisés du socle.

## Cycle d'une mission

```text
mission_created
  -> mission_started
  -> mission_planned
  -> task_started / task_completed (pour chaque agent)
  -> mission_reviewed
  -> report_ready
  -> mission_completed
```

## Validation

| Test | Résultat |
|---|---|
| Création d'une mission sans exécution automatique | réussi |
| Mission d'analyse avec rapport | réussi |
| Campagne complète API + UI | réussi |
| Approbation obligatoire pour mission sensible | réussi |
| Journal d'événements réel et ordonné | réussi |

**5 tests sur 5 réussis.**

## Mission de démonstration

- ID : `4e1c01636615`
- Statut : `completed`
- Agents exécutés : QA Analyst, Test Designer, API Tester, API Automation, UI Automation, QA Reporter
- Rapport : `reports/missions/4e1c01636615.md`
- Aucun test réel exécuté, aucune anomalie inventée.

## Limites volontaires de cette phase

- Les agents produisent des plans, pas encore des exécutions réelles.
- Aucun appel LLM n'est encore effectué.
- Telegram n'est pas encore connecté.
- Les tests API/UI réels seront branchés en phases 5 et 6.
- Les rapports Allure seront branchés en phase 7.

## Garde-fous vérifiés

- Une mission n'est jamais créée automatiquement.
- Une mission sensible passe en `waiting_approval` et ne crée aucune tâche avant approbation.
- Le rapport précise explicitement qu'aucun test réel n'a été exécuté.
- Le Manager ne déclare aucune anomalie sans preuve.

## Prochaine étape

Phase 4 — veilleur Telegram minimal, allowlist, polling et démarrage du Manager uniquement sur message autorisé.
