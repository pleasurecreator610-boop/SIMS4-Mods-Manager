# Fournisseur Officiel Deaderpool (`deaderpool`)

Le fournisseur `deaderpool` assure l'indexation, la résolution prioritaire de dépendances et le téléchargement direct des modules officiels **MC Command Center (MCCC)** et **MC WooHoo** depuis le portail officiel de Deaderpool.

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `deaderpool`
- **Classe d'Implémentation** : [`plugins/deaderpool/provider.py`](../../plugins/deaderpool/provider.py) (`DeaderpoolProvider`, héritant de `BasePortalProvider`)
- **URL Officielle** : `https://deaderpool-mccc.com`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur Requis** : **Aucun** (`PUBLIC_NO_ACCOUNT_PROVIDERS`)
- **Commentaires / MP** : Non applicable (portail officiel de distribution)

---

## 2. Catégories & Modules Officiels

1. **MC Command Center (`mccc_main`)** :
   - Module central d'administration, de progression de l'histoire et de contrôle d'autonomie pour Les Sims 4 (`deaderpool_mccc`).
2. **MC WooHoo (`mc_woohoo`)** :
   - Module complémentaire officiel dédié aux interactions romantiques et de crac-crac (`deaderpool_mc_woohoo`).

---

## 3. Interception Prioritaire des Dépendances (`SPECIAL_DEPENDENCY_CASES`)

Tout mod (quelle que soit sa plateforme d'origine : LoversLab, CurseForge, ModTheSims, Patreon, F95zone, etc.) déclarant un prérequis parmi :
- `MCCC`, `MC Command Center`, `Deaderpool MCCC`, `mc_cmd_center`
- `MC WooHoo`, `MCWooHoo`, `mc_woohoo`

est **automatiquement redirigé** vers le provider officiel `deaderpool` (`https://deaderpool-mccc.com/downloads.html#mccc` ou `#mcwoohoo`), garantissant un téléchargement direct sans compte depuis la source officielle.

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](../../tests/unit/providers/test_new_platforms_providers.py) : Découverte `ProviderRegistry`, `scrape_category_page`, `get_mod_details`, `download_mod_file` (validation ZIP et rejet HTML).
- [`tests/unit/application/test_multi_platform_dependencies_and_dedup.py`](../../tests/unit/application/test_multi_platform_dependencies_and_dedup.py) : Redirection prioritaire de CurseForge/LoversLab vers `deaderpool` et déduplication inter-plateformes.

