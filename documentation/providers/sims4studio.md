# Fournisseur Sims 4 Studio (`sims4studio`)

Le fournisseur `sims4studio` intègre le forum officiel **Sims 4 Studio** (`sims4studio.com`), source officielle d'**Andrew's Pose Player**, de **Teleport Any Sim** et des galeries **Creator Studios**.

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `sims4studio`
- **Classe d'Implémentation** : [`plugins/sims4studio/provider.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/plugins/sims4studio/provider.py) (`Sims4StudioProvider`)
- **URL Officielle** : `https://sims4studio.com`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur** : Optionnel (`ACCOUNT_SUPPORTED_PROVIDERS`) — utilisé pour accéder aux fils restreints du forum ProBoards et publier des commentaires ou envoyer des messages privés aux créateurs.

---

## 2. Catégories & Frameworks Officiels

- **Andrew's Studio & Core Mods (`s4s_andrew_studio`)** :
  - **Andrew's Pose Player (`s4s_pose_player`)** : Intercepté automatiquement via `SPECIAL_DEPENDENCY_CASES` dès qu'un pack de poses le requiert.
  - **Teleport Any Sim** & **Studio Effect Player**.
- **Creator Studios (`s4s_creator_studios`)** : Catalogue communautaire de poses, animations, CAS et objets.

---

## 3. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_new_platforms_reporting_and_comments.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/application/test_new_platforms_reporting_and_comments.py)

