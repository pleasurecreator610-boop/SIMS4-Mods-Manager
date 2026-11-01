# Fournisseur GameBanana (`gamebanana`)

Le fournisseur `gamebanana` connecte **SIMS 4 Mods Manager** à la section **The Sims 4 (Game ID `5496`)** de **GameBanana** via son API REST publique Core v11 et son parseur HTML de secours.

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `gamebanana`
- **Classe d'Implémentation** : [`plugins/gamebanana/provider.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/plugins/gamebanana/provider.py) (`GameBananaProvider`)
- **URL Officielle** : `https://gamebanana.com/games/5496`
- **API JSON** : `https://gamebanana.com/apiv11/Mod/Index?_aFilters[Generic_Game]=5496`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur** : Optionnel (`ACCOUNT_SUPPORTED_PROVIDERS`) — requis uniquement pour poster des commentaires ou envoyer un MP à un auteur.

---

## 2. Catégories Prises en Charge

- **Scripts & Gameplay (`gb_scripts`)**
- **Skins, CAS & Cosmetics (`gb_skins_cas`)**
- **UI, Sounds & Overhauls (`gb_ui_effects`)**

---

## 3. Gestion des Commentaires & Signalement Créateurs

Compatible avec `RequirementReporterService` :

- Vérifie l'authentification via `SessionManager.is_member_authenticated("gamebanana")`.
- Invite l'utilisateur à se connecter si nécessaire, puis permet de publier un commentaire ou d'ouvrir un message privé (`https://gamebanana.com/pm/add?recipient={creator_id}`).

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_new_platforms_reporting_and_comments.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/application/test_new_platforms_reporting_and_comments.py)

