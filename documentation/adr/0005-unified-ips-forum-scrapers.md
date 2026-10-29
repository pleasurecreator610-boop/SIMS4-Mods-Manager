# ADR 0005 : Architecture Mutualisée des Fournisseurs de Forums IPS (Invision Community)

- **Statut** : Accepté
- **Date** : 2026-10-29

## Contexte
LoversLab et NSFWMods partagent le même moteur de forum sous-jacent (Invision Community Suite / IPS4), avec des structures HTML similaires pour la pagination, l'affichage des sujets, la détection des pièces jointes et la publication de commentaires.

## Décision
1. Création de la classe d'abstraction `BaseIPSForumProvider` dans `src/providers/common/ips_base.py`.
2. Mutualisation de l'analyse des tokens CSRF (`csrfKey`), du parsing des dates relatives et des sélecteurs CSS communs.
3. Spécialisation dans les plugins respectifs `plugins/loverslab` et `plugins/nsfwmods` pour leurs particularités de catégories et d'authentification.
