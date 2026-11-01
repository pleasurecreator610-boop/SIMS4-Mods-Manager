# Fournisseur LittleMsSam (`littlemssam`)

Le fournisseur `littlemssam` indexe le portail officiel de **LittleMsSam** (`lms-mods.com`), qui regroupe plus de 200 mods de gameplay, correctifs et améliorations de qualité de vie pour Les Sims 4.

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `littlemssam`
- **Classe d'Implémentation** : [`plugins/littlemssam/provider.py`](../../plugins/littlemssam/provider.py) (`LittleMsSamProvider`)
- **URL Officielle** : `https://lms-mods.com`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur Requis** : **Aucun** (`PUBLIC_NO_ACCOUNT_PROVIDERS`)

---

## 2. Catégories Prises en Charge

- **Gameplay Overhauls (`lms_gameplay`)** : *More Buyable Venues*, *Live in Business*, *Foster Family*, *Ultrasound Scan*, *SimDa Dating App*.
- **Random Small Mods (`lms_rsm`)** & **Random Bug Fixes (`lms_bugfixes`)**.

---

## 3. Déduplication avec CurseForge

LittleMsSam distribuant également ses mods sur CurseForge, `ModMatcher.canonical_fingerprint` garantit qu'un mod installé depuis `littlemssam` est reconnu comme déjà installé sur `curseforge` (et inversement).

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](../../tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_multi_platform_dependencies_and_dedup.py`](../../tests/unit/application/test_multi_platform_dependencies_and_dedup.py)

