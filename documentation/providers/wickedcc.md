# Fournisseur Officiel Wicked.cc / TURBODRIVER (`wickedcc`)

Le fournisseur `wickedcc` connecte **SIMS 4 Mods Manager** au portail officiel de **TURBODRIVER** (`wicked.cc` / `wickedwhims.com` / `wonderfulwhims.com`).

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `wickedcc`
- **Classe d'Implémentation** : [`plugins/wickedcc/provider.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/plugins/wickedcc/provider.py) (`WickedCcProvider`, héritant de `BasePortalProvider`)
- **URL Officielle** : `https://wicked.cc`
- **Contenu Adulte (`+18`)** : Oui (masqué lorsque le filtre `+18` est désactivé)
- **Compte Utilisateur Requis** : **Aucun** (`PUBLIC_NO_ACCOUNT_PROVIDERS`) — Téléchargement public direct sans passer par le mur d'authentification de LoversLab.

---

## 2. Catégories & Modules Officiels

1. **WickedWhims Official (`wickedwhims_core`, ID `3169`)** : Framework officiel complet (`https://wicked.cc/download/3169-wickedwhims/`).
2. **WonderfulWhims Official (`wonderfulwhims_official`)** : Version SFW officielle axée sur l'attraction, la personnalité et le cycle menstruel (`https://wonderfulwhims.com/`).
3. **WickedWhims Animations Directory (`ww_animations`)** : Répertoire officiel des créateurs d'animations référencés sur `wicked.cc`.

---

## 3. Interception Prioritaire des Dépendances (`SPECIAL_DEPENDENCY_CASES`)

Toutes les variantes (`WW`, `ww`, `WickedWhims`, `Wicked-Whims`, `Wicked_Whims`, `Wicked Whims`, `WickedWhile`, ou un lien `loverslab.com/files/file/3169-wickedwhims/`) sont **interceptées en priorité absolue** et redirigées vers `source="wickedcc"`, `remote_id="3169"`, `url="https://wicked.cc/download/3169-wickedwhims/"`.

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_dependency_resolver.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/application/test_dependency_resolver.py)
- [`tests/unit/application/test_multi_platform_dependencies_and_dedup.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/tests/unit/application/test_multi_platform_dependencies_and_dedup.py)

