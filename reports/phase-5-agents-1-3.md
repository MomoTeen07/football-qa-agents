# Phase 5 — Agents 1 à 3 (Gemini, Postman, API réelle)

Date : 9 novembre 2026

## Objectif

Rendre réels les trois premiers agents du système, sans modifier les
fonctionnalités existantes :

1. **QA Analyst** — analyse et stratégie de test.
2. **Test Designer** — conception des cas de test et traçabilité.
3. **API Tester** — analyse OpenAPI réelle, collection Postman réelle et
   premiers tests API réels sur la stack de test isolée.

Les agents 4 à 7 restent des stubs de planification.

## Composants créés

| Fichier | Rôle |
|---|---|
| `app/llm/__init__.py` | Package d'intégration LLM. |
| `app/llm/gemini.py` | Client REST Gemini free tier, sans SDK payant. |
| `app/tools/__init__.py` | Package des outils réels. |
| `app/tools/workspace.py` | Écriture des preuves UTF-8 dans le workspace de mission. |
| `app/tools/openapi_postman.py` | Analyse OpenAPI, génération collection et environnement Postman. |
| `app/tools/api_probe.py` | Sondes HTTP réelles, preuves JSON/Markdown, anomalies reproductibles. |
| `app/agents/phase5.py` | Agents 1 à 3 réels, avec repli déterministe. |
| `scripts/run_phase5_mission.py` | Lanceur explicite d'une mission phase 5. |
| `tests/test_gemini_client.py` | 5 tests du client Gemini. |
| `tests/test_openapi_postman.py` | 3 tests de l'analyse OpenAPI et de Postman. |
| `tests/test_api_probe.py` | 4 tests des sondes, du garde-fou et des anomalies. |
| `tests/test_phase5_agents.py` | 6 tests des agents et du reporter. |

Fichiers modifiés :

- `app/config.py` : flags phase 5, comptes de test, délais, chemins Postman.
- `app/orchestrator/manager.py` : injection du client Gemini et des sondes.
- `app/orchestrator/graph.py` : le contexte du reporter transporte désormais
  les résultats et les preuves des tâches.
- `app/agents/stubs.py` : le reporter lit `probe-results.json` et ne déclare
  une anomalie que sur preuve réelle.
- `.env.example` : `LLM_MODEL=gemini-3.5-flash`, `REAL_AGENTS_ENABLED=false`.
- `tests/test_manager.py` : les tests existants forcent
  `real_agents_enabled=False` pour rester hermétiques.

## Gemini free tier

- Client REST minimal : `models/{model}:generateContent`.
- Aucun SDK payant, aucune carte bancaire.
- La clé est lue dans `.env` et n'est **jamais** journalisée, affichée ni
  incluse dans un message d'erreur.
- Les erreurs sont réduites au type ou au code HTTP.
- Repli déterministe si la clé est absente ou si l'appel échoue : la mission
  continue, sans inventer de contenu ni d'anomalie.
- `thinkingBudget=0` est activé pour les modèles Gemini 3 afin de réduire la
  latence et la consommation du free tier.

### Changement de modèle

`gemini-2.5-flash` et `gemini-2.5-flash-lite` renvoient désormais HTTP 404
pour ce compte :

```
NOT_FOUND — This model ... is no longer available to new users.
```

Le modèle retenu et validé réellement est **`gemini-3.5-flash`**. La valeur
par défaut de `app/config.py`, `.env.example` et `.env` a été alignée.
Aucune clé n'a été affichée pendant la validation.

## Collection Postman réelle

Générée depuis l'OpenAPI réel de `http://localhost:8002/openapi.json` :

- `postman/collections/football-qa.json`
- `postman/environments/football-qa-test.json`

Caractéristiques :

- 11 requêtes réellement exposées par l'API ;
- dossiers `health`, `auth`, `users`, `favorites`, `football` ;
- variables `baseUrl`, `token`, `favoriteId`, `testUserEmail`,
  `testUserPassword` ;
- en-tête `Authorization: Bearer {{token}}` uniquement sur les opérations
  protégées par `HTTPBearer` ;
- scripts de test Postman : statut attendu, réponse JSON, mémorisation du
  jeton après login/register et de l'identifiant de favori après création ;
- exemples de corps réalistes pour l'inscription, la connexion et l'ajout d'un
  favori.

L'environnement contient les comptes de test locaux, pas les secrets
Telegram/Gemini.

## Sondes API réelles

Outil : `app/tools/api_probe.py`.

Garde-fou : la cible doit être `http://localhost:8002` ou
`http://127.0.0.1:8002`. Toute autre cible, y compris l'application réelle sur
`8001`, est refusée par `UnsafeTargetError` avant toute requête.

Les sondes exécutent 21 vérifications :

| Domaine | Vérifications |
|---|---|
| Santé | `GET /health` → 200 |
| Football | leagues (6), standings, matches, détail équipe 57, ligue inconnue → 404 |
| Authentification | connexion utilisateur 1 et 2, jeton présent |
| Utilisateurs | `GET /api/users/me` avec jeton, sans jeton → 401 |
| Erreurs auth | mauvais mot de passe → 401, email existant → 409, mot de passe court → 422 |
| Favoris | liste, création 201, doublon 409, visibilité propriétaire, isolation entre utilisateurs, suppression croisée → 404, suppression propriétaire → 204, absence après suppression |

Les preuves sont écrites en UTF-8 dans le workspace :

- `workspace/missions/<id>/api/probe-results.json`
- `workspace/missions/<id>/api/probe-report.md`
- `workspace/missions/<id>/api/openapi.json`
- `workspace/missions/<id>/api/openapi-analysis.json`

Les données sensibles sont expurgées avant écriture : mots de passe, jetons,
en-têtes d'autorisation et clés sont remplacés par `[redacted]`.

Une anomalie n'est créée que si une vérification exécutée échoue. Chaque
anomalie contient la méthode, le chemin, l'attendu, l'obtenu, une commande de
reproduction et un extrait de réponse. Une sonde non exécutable produit un
statut `blocked` et **aucune** anomalie applicative.

Aucun nettoyage destructif global n'est effectué : seuls les favoris de sonde
résiduels (`team_id=999001`) sont supprimés.

## Résultats des tests

```powershell
.venv\Scripts\python.exe -m pytest
# 41 passed
```

| Catégorie | Nombre |
|---|---:|
| Tests existants du socle Manager | 5 |
| Tests allowlist Telegram | 5 |
| Tests gateway Telegram | 13 |
| Tests client Gemini | 5 |
| Tests OpenAPI / Postman | 3 |
| Tests sondes API | 4 |
| Tests agents phase 5 et reporter | 6 |
| **Total** | **41** |

## Mission réelle de validation

Mission : `b745b4a199b7`, lancée explicitement via
`scripts/run_phase5_mission.py`.

Instruction : « Analyse l'API réelle, prépare la collection Postman et exécute
les premiers tests API sur la stack de test isolée. »

Résultat :

- statut final : `completed` ;
- tâches `qa_analyst`, `test_designer`, `api_tester`, `api_automation`,
  `qa_reporter` : `completed` ;
- sondes : **21/21 réussies**, 0 ignorée, **0 anomalie** ;
- analyse OpenAPI : 11 opérations, 8 schémas ;
- collection Postman : 11 requêtes, 5 dossiers ;
- base de test nettoyée après la mission : favoris `qa.user1` = 0,
  `qa.user2` = 0 ;
- rapport : `reports/missions/b745b4a199b7.md` ;
- preuves : `workspace/missions/b745b4a199b7/`.

Les trois analyses Gemini sont conservées :

- `workspace/missions/b745b4a199b7/analysis/qa-analyst-gemini.md`
- `workspace/missions/b745b4a199b7/design/test-designer-gemini.md`
- `workspace/missions/b745b4a199b7/api/api-tester-gemini.md`

## Garde-fous vérifiés

- Aucune mission automatique, aucun scheduler, aucun cron.
- Aucune écriture dans la base réelle ; cible limitée à `localhost:8002`.
- Aucun secret affiché, journalisé ou inclus dans une preuve.
- Les tests existants restent hermétiques : `real_agents_enabled=False`.
- Les agents 4 à 7 restent inchangés.
- Aucune anomalie inventée : le reporter ne s'appuie que sur les preuves
  réellement présentes.

## Limites connues

- La phase 5 couvre l'API, pas l'UI : Playwright et les tests UI relèvent de la
  phase 6.
- L'inscription nominale d'un nouvel utilisateur (201 puis connexion) n'est pas
  encore dans les sondes ; elle est identifiée comme test prioritaire.
- La validation stricte des schémas JSON de réponse et les jetons JWT
  malformés/expirés restent à couvrir.
- Les agents 4 à 7 sont toujours des stubs de planification.
- Le test réel du bot Telegram avec le token désormais présent reste optionnel
  et n'a pas été inclus dans cette validation automatique.
