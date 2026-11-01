# Fournisseur itch.io (`itchio`)

Le fournisseur `itchio` permet d'explorer et de télécharger les mods indépendants, outils et créations pour **Les Sims 4** hébergés sur **itch.io** (`tag-sims-4` / `tag-the-sims-4`).

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `itchio`
- **Classe d'Implémentation** : [`plugins/itchio/provider.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/plugins/itchio/provider.py) (`ItchIoProvider`)
- **URL Officielle** : `https://itch.io/games/tag-sims-4`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur** : Optionnel (`ACCOUNT_SUPPORTED_PROVIDERS`) — requis uniquement pour poster un commentaire sur la page d'un créateur ou accéder à des téléchargements membres.

---

## 2. Catégories Prises en Charge

- **Sims 4 Mods & Gameplay (`itch_sims4_mods`)**
- **Tools, CC & Custom Assets (`itch_sims4_tools`)**

---

## 3. Gestion des Commentaires & Signalement Créateurs

Supporte la vérification d'authentification, la détection anti-doublon, la publication et la suppression de commentaires via `RequirementReporterService`.

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_new_platforms_reporting_and_comments.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/application/test_new_platforms_reporting_and_comments.py)

