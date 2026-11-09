# Phase 2 — Isolation de l'environnement de test

Date : 9 novembre 2026

## Stack de test

| Service | URL | État |
|---|---|---|
| Frontend de test | http://localhost:5175 | 200 |
| API de test | http://localhost:8002 | 200, `{"status":"ok"}` |
| PostgreSQL de test | localhost:5434 | healthy |
| Swagger | http://localhost:8002/docs | 200 |

La stack utilise `MOCK_FOOTBALL_API=true` et un volume PostgreSQL dédié.

## Isolation vérifiée

| Base | Utilisateurs | Favoris |
|---|---|---|
| Base réelle `footballqa` | 5 | 2 |
| Base de test `footballqa_test` | 2 | 0 |

Les compteurs de la base réelle sont identiques à ceux du baseline : aucune écriture n'a eu lieu dans la base réelle.

## Comptes de test

- `qa.user1@example.com`
- `qa.user2@example.com`

Les mots de passe sont des mots de passe de test, stockés hors Git dans `.env.test` lors de l'exploitation.

## Suites rejouées contre la stack de test

| Suite | Résultat |
|---|---|
| Tests de contrat API sur `8002` | 2 réussis |
| Test UI « championships are visible » sur `5175` | 1 réussi |

## Point corrigé

Le validateur d'email de l'application refuse les domaines réservés `.test`. Les comptes utilisent donc `example.com`, accepté par l'application.

## Conclusion

La phase 2 est validée. Les agents pourront travailler sur une base jetable sans risque pour les données réelles.
