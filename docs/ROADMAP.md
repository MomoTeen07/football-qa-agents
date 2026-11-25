# Feuille de route

État au **25/11/2026**. Version courante : `0.9.1`.

Les 9 phases de construction sont terminées. Ce qui reste n'est pas de la fonctionnalité :
c'est de la **reproductibilité**.

## Point bloquant à traiter en premier

- [ ] **Rendre la stack de test autonome.** `infra/docker-compose.test.yml` construit
      l'application cible depuis `../../MyFinalProject/backend` et `../../MyFinalProject/frontend`,
      deux dossiers absents du dépôt public. Tant que ce n'est pas corrigé, personne ne peut
      reproduire une mission sans posséder l'arborescence locale d'origine.
      Piste : pointer vers `../../football-qa/` (dépôt public) ou accepter un chemin en variable
      d'environnement avec valeur par défaut.

## Qualité et preuves

- [ ] Capture d'écran du bureau virtuel 2D dans le README (preuve visuelle du résultat)
- [ ] Publier un exemple de rapport Allure généré (résultats figés, sans secret)
- [ ] Badge de couverture sur `app/` et `tests/`
- [ ] `mypy` en CI en mode `continue-on-error` d'abord, bloquant ensuite

## Avant de passer en 1.0

- [ ] La stack de test se construit depuis un clone du seul dépôt public
- [ ] Un parcours complet (Telegram → mission → rapport) est documenté pas à pas avec captures
- [ ] Les garde-fous de sécurité ont un test dédié par règle (chemins, refs Git, secrets, cibles réseau)
- [ ] `docs/GUIDE.md` ne contient plus de référence à une machine ou à un utilisateur local précis

## Explicitement hors périmètre

- Déploiement multi-utilisateur, file d'attente distribuée, interface web d'administration.
- Ajout d'agents supplémentaires : le graphe actuel couvre le cycle de test de bout en bout.
