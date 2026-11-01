# Fournisseur Officiel Scumbumbo (`scumbumbo`)

Le fournisseur `scumbumbo` connecte **SIMS 4 Mods Manager** au portail commémoratif officiel **Scumbumbo Mods** (`scumbumbomods.com`), maintenu par la communauté des créateurs Sims 4 (Triplis, LittleMsSam, Basemental, Turbodriver).

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `scumbumbo`
- **Classe d'Implémentation** : [`plugins/scumbumbo/provider.py`](../../plugins/scumbumbo/provider.py) (`ScumbumboProvider`, héritant de `BasePortalProvider`)
- **URL Officielle** : `https://scumbumbomods.com`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur Requis** : **Aucun** (`PUBLIC_NO_ACCOUNT_PROVIDERS`)
- **Commentaires / MP** : Non applicable (portail officiel de référence)

---

## 2. Catégories & Frameworks Officiels

- **XML Injector (`scumbumbo_xml_injector`)** : Bibliothèque d'injection de tuning XML indispensable à des centaines de mods Sims 4 (`https://scumbumbomods.com/xml-injector`).
- **Teleport Any Sim (`scumbumbo_teleport_any_sim`)** : Statue de téléportation indispensable pour les packs de poses et d'animations (`https://scumbumbomods.com/teleport-any-sim`).
- **Don't Wash Dishes Where You Angry Poop**, **Don't Prep Food Where You Angry Poop**, **Keep Instruments in Inventory**, **Packing Crates**, **Working Alarm Clocks**, **Always Keep a Doctor at the Hospital**.

---

## 3. Interception Prioritaire des Dépendances (`SPECIAL_DEPENDENCY_CASES`)

Toute mention de `XML Injector`, `Scumbumbo's XML Injector`, `xmlinjector` ou `Teleport Any Sim` dans les prérequis d'un mod (même si l'auteur a inséré un lien vers CurseForge ou ModTheSims) est systématiquement interceptée et résolue vers `scumbumbomods.com`.

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](../../tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_multi_platform_dependencies_and_dedup.py`](../../tests/unit/application/test_multi_platform_dependencies_and_dedup.py)

