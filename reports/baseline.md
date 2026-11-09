# Baseline — application football-qa

Date : 9 novembre 2026

## Environnement

- Application : `C:\Users\stgadmin\Desktop\football-qa`
- Frontend : React / Vite, `http://localhost:5174`
- API : FastAPI, `http://localhost:8001`
- PostgreSQL : `localhost:5433`, base `footballqa`
- Docker Compose : backend, frontend et base en état `Up`
- Mode football : API réelle (`MOCK_FOOTBALL_API=false`)

## Vérifications

| Vérification | Résultat |
|---|---|
| `GET /health` | 200, `{"status":"ok"}` |
| Interface web `/` | 200 |
| Swagger `/docs` | 200 |
| `GET /api/football/leagues` | 200, 6 championnats |
| Utilisateurs en base réelle | 5 |
| Favoris en base réelle | 2 |

## Suites existantes

| Suite | Résultat |
|---|---|
| Tests backend pytest | 4 réussis |
| Tests de contrat API | 2 réussis |
| Tests UI Playwright | 1 réussi, 1 échec de test |

## Analyse de l'échec Playwright

Le test `home displays football QA` échoue pour une raison de **locator ambigu** :

- `getByText('Football QA')` trouve trois éléments : le lien de marque, un titre et le pied de page.
- Playwright applique le mode strict et refuse le choix automatique.

Ce n'est pas une anomalie fonctionnelle de l'application. Le test doit cibler un élément précis, par exemple le lien de marque ou un rôle accessible.

Le second test, `championships are visible`, passe : 6 cartes de championnat sont affichées.

## Points relevés

- Les tests backend ne sont pas copiés dans l'image Docker ; ils ont été exécutés via un montage temporaire.
- Le dépôt Git de l'application est resté propre après exécution.
- Aucune donnée n'a été écrite dans la base réelle pendant le baseline.
- La base de test n'existait pas encore ; elle est créée en phase 2.

## Conclusion

L'application est opérationnelle et testable. La couverture existante est faible et devra être complétée par les agents. La stack de test isolée est la prochaine étape.
