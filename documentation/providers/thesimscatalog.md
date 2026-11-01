# Fournisseur The Sims Catalog (`thesimscatalog`)

Le fournisseur `thesimscatalog` indexe et télécharge les mods de gameplay, traits, carrières et créations CC depuis **The Sims Catalog** (`thesimscatalog.com/sims4/`).

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `thesimscatalog`
- **Classe d'Implémentation** : [`plugins/thesimscatalog/provider.py`](../../plugins/thesimscatalog/provider.py) (`TheSimsCatalogProvider`)
- **URL Officielle** : `https://thesimscatalog.com/sims4/`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur Requis** : **Aucun** (`PUBLIC_NO_ACCOUNT_PROVIDERS`)

---

## 2. Catégories Prises en Charge

- **Game Mods & Careers (`tsc_game_mods`)**
- **Traits & Aspirations (`tsc_traits`)**
- **Hairstyles & CAS (`tsc_hair_cas`)**
- **Furniture & Build/Buy (`tsc_furniture`)**

---

## 3. Déduplication Inter-Plateformes

Les mods indexés sur The Sims Catalog qui référencent ou dupliquent des créations déjà installées depuis ModTheSims, CurseForge ou LittleMsSam sont automatiquement reconnus par `ModMatcher.canonical_fingerprint` pour éviter tout doublon.

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](../../tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_multi_platform_dependencies_and_dedup.py`](../../tests/unit/application/test_multi_platform_dependencies_and_dedup.py)

