# Phase 8 — Bureau virtuel 2D

**Statut : terminée** (11 novembre 2026).  
Point de départ : `main` `dad1b63` (phase 7), 90 tests verts.  
Livraison : phase 8 fusionnée par la PR #13 (`97b213e`), **103 tests verts**.

Ce rapport comble le constat R14 du plan de phase 9 (« pas de rapport de
phase 8 »). Il résume ce qui a été livré et ce qui reste vrai après le
durcissement.

---

## 1. Objectif

Représenter les huit agents réels dans un bureau virtuel 2D, alimenté
**uniquement** par les missions, tâches et événements persistés. Aucune
animation décorative, aucune donnée simulée, aucun lancement de mission depuis
le navigateur.

---

## 2. Livré

- **Frontend statique** `office/` : HTML/CSS/JS natifs, aucun build, aucun
  framework, aucune ressource distante.
  - `index.html`, `assets/styles.css`
  - `layout.js` : géométrie isométrique, postes, zones, décor
  - `sprites.js` : sprites pixel art des 8 agents
  - `scene.js` : scène SVG, tri en profondeur, déplacements
  - `app.js` : SSE, rendu, panneaux, bulles, fiche agent
- **Catalogue** `app/office/catalog.py` : huit personnages aux identifiants
  identiques à ceux du planificateur et du graphe (Manager QA, QA Analyst,
  Test Designer, API Tester, API Automation, UI Automation, DevOps,
  QA Reporter), six départements.
- **État réel** `app/office/state.py` : mission courante, statuts d'agents,
  progression, tâches, preuves, synthèse Allure, événements et activité
  récente.
- **Passations réelles** : déduites uniquement des dépendances `depends_on`
  dont la tâche amont est terminée et portée par un autre agent.
- **Flux** `app/office/stream.py` : abonnement à l'`EventBus` en mémoire **et**
  relecture du journal SQLite, dédupliqués par identifiant. Fonctionne quand le
  gateway Telegram tourne dans un autre processus.
- **Serveur local** `app/office/server.py` : `ThreadingHTTPServer` de la
  bibliothèque standard, routes `/`, `/api/state`, `/api/missions`, `/events`
  (SSE), `/api/health`.
- **Lanceur** `scripts/run_office.py` : `--mission-id`, `--port`, `--open`.
  Lecture seule, aucune création ni exécution de mission.
- **Tests** `tests/test_office.py` (13) : catalogue, statuts, passations,
  Allure, flux mémoire/SQLite, endpoints, SSE, refus d'une interface non
  locale, traversée de chemins, absence de `Math.random` / `setInterval` / URL
  externe, présence de `key` dans les événements de tâche.

---

## 3. Garanties

- Écoute strictement locale (`127.0.0.1`, `localhost`, `::1`) ; toute autre
  interface est refusée.
- Aucune écriture : ni mission, ni tâche, ni événement, ni base applicative.
- Aucun secret exposé ; depuis la phase 9, `/api/state`, `/api/missions` et le
  SSE passent par `redact_structure` avec les secrets connus.
- Aucune animation aléatoire ; sans mission, les huit agents restent
  disponibles et silencieux.
- Une seule bulle par agent, quatre au maximum ; file d'animations bornée.
- Frontend sans `Math.random`, sans `setInterval`, sans URL externe (le
  namespace SVG est la seule occurrence `http://` tolérée).

---

## 4. Limites et suite

- Le bureau dépend du store SQLite local : sans mission, l'état est vide.
- Le rendu HTML Allure reste optionnel (CLI Allure gratuite, non requise).
- Depuis la phase 9 : limite de 12 flux SSE, `503` au-delà, timeout d'écriture,
  en-têtes de sécurité sur toutes les réponses et `405` pour les méthodes non
  `GET`.
- Aucune fonctionnalité de pilotage (création, approbation, annulation) n'est
  exposée dans le navigateur : le pilotage reste Telegram ou CLI.

---

## 5. Vérification

```powershell
.venv\Scripts\python.exe scripts\run_office.py --mission-id <id>
# Bureau virtuel : http://127.0.0.1:5180/
.venv\Scripts\python.exe -m pytest tests/test_office.py tests/test_office_security.py
```
