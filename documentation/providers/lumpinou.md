# Fournisseur Officiel Lumpinou (`lumpinou`)

Le fournisseur `lumpinou` intègre le portail officiel **Lumpinou Mods** (`lumpinoumods.com`), source canonique des grands mods relationnels et des bibliothèques partagées de Lumpinou.

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `lumpinou`
- **Classe d'Implémentation** : [`plugins/lumpinou/provider.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/plugins/lumpinou/provider.py) (`LumpinouProvider`, héritant de `BasePortalProvider`)
- **URL Officielle** : `https://www.lumpinoumods.com`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur Requis** : **Aucun** (`PUBLIC_NO_ACCOUNT_PROVIDERS`)

---

## 2. Frameworks & Mods Officiels Pris en Charge

1. **Relationship & Pregnancy Overhaul (RPO / WooHoo Wellness)** (`lumpinou_rpo_collection`)
2. **Lumpinou's Mood Pack Mod** (`lumpinou_mood_pack`) — Prérequis très fréquent pour les mods de gameplay, carrières et traits personnalisés.
3. **Lumpinou's Toolbox** (`lumpinou_toolbox`) — Bibliothèque technique requise par les mods de Lumpinou et de créateurs tiers.
4. **LGBTQIA+ Mod (Gender & Orientation Overhaul)** (`lumpinou_lgbtqia`)
5. **Open Love Life**, **First Impressions**, **Talents & Weaknesses**, **Milestones Expanded**, **Road to Romance**, **SimInfo Manager**.

---

## 3. Interception Prioritaire des Dépendances (`SPECIAL_DEPENDENCY_CASES`)

Les dépendances nommées `RPO`, `Relationship & Pregnancy Overhaul`, `WooHoo Wellness`, `Mood Pack Mod`, `Lumpinou's Toolbox` ou `LGBTQIA+ Mod` sont systématiquement routées vers `lumpinoumods.com`.

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_multi_platform_dependencies_and_dedup.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/application/test_multi_platform_dependencies_and_dedup.py)

