# Fournisseur NSFWMods (IPS4)

Le fournisseur `nsfwmods` gère la synchronisation du catalogue de la plateforme **NSFWMods**, les pièces jointes, les catégories Sims 4 et l'intégration du forum Invision Community (IPS4).

---

## 1. Caractéristiques Principales

- **Endpoint Officiel** : `https://nsfwmods.com/files/category/287-sims-mods/`
- **Moteur IPS4 Partagé** : Hérite de `BaseIPSForumProvider` (`src/providers/common/ips_base.py`) en partageant la résolution CSRF, les formulaires de commentaires et la messagerie privée.
- **11 Catégories Sims 4 Prises en Charge** :
  1. Sims Mods (`287-sims-mods`)
  2. Adult (`364-adult`)
  3. Clothing (`289-clothing`)
  4. Shoes (`296-shoes`)
  5. Accessories (`292-accessories`)
  6. Body Types (`288-body-types`)
  7. Hair (`290-hair`)
  8. Skintones (`294-skintones`)
  9. Facial Hair (`295-facial-hair`)
  10. Makeup (`291-makeup`)
  11. Eyes (`293-eyes`)

---

## 2. Filtrage "Contenu Adulte (+18)"

Par défaut, l'option `adult_content_enabled` de l'application est désactivée.
Lorsqu'elle est désactivée :

- Les modules en provenance de **NSFWMods** et de **LoversLab** sont masqués du catalogue unifié.
- Les cartes d'authentification associées dans l'onglet *Comptes* sont repliées.
- Un bandeau discret permet à l'utilisateur d'activer le contenu adulte d'un simple clic.
