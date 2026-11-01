# Fournisseur Synthira.ru (`synthira` • `+18`)

Le fournisseur `synthira` connecte **SIMS 4 Mods Manager** à la section **The Sims 4 (`+18`)** du portail **Synthira.ru** (`synthira.ru/load/12`).

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `synthira`
- **Classe d'Implémentation** : [`plugins/synthira/provider.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/plugins/synthira/provider.py) (`SynthiraProvider`)
- **URL Officielle** : `https://synthira.ru/load/12`
- **Contenu Adulte (`+18`)** : Oui (`ADULT_PROVIDERS` — masqué par défaut, affiché lorsque le filtre `+18` est activé)
- **Compte Utilisateur** : Optionnel (`ACCOUNT_SUPPORTED_PROVIDERS`) — utilisé pour poster des commentaires et envoyer des messages aux auteurs.

---

## 2. Catégories & Dépendances

- **Sims 4 Adult Mods & Animations (`synthira_sims4_main`)**
- **Gameplay & Translations (`synthira_sims4_gameplay`)**
- Toute dépendance vers *WickedWhims*, *MCCC*, *XML Injector*, *Lumpinou* ou *Basemental* est automatiquement redirigée vers son site officiel via `SPECIAL_DEPENDENCY_CASES`.

---

## 3. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_new_platforms_reporting_and_comments.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/application/test_new_platforms_reporting_and_comments.py)

