# Fournisseur Officiel Basemental (`basemental`)

Le fournisseur `basemental` intègre le site officiel **Basemental CC** (`basementalcc.com`) pour le téléchargement direct des frameworks et mods de Basemental.

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `basemental`
- **Classe d'Implémentation** : [`plugins/basemental/provider.py`](../../plugins/basemental/provider.py) (`BasementalProvider`, héritant de `BasePortalProvider`)
- **URL Officielle** : `https://basementalcc.com`
- **Contenu Adulte (`+18`)** : Oui (`ADULT_PROVIDERS`)
- **Compte Utilisateur Requis** : **Aucun** (`PUBLIC_NO_ACCOUNT_PROVIDERS`)

---

## 2. Modules Officiels Pris en Charge

1. **Basemental Drugs (`basemental_drugs`)** : `https://basementalcc.com/adult_mods/basemental-drugs/`
2. **Basemental Gangs (`basemental_gangs`)** : `https://basementalcc.com/adult_mods/basemental-gangs/`
3. **Basemental Universal Venue List (`basemental_universal_venue_list`)** : Liste universelle de types de terrains partagée avec de nombreux autres créateurs (`https://basementalcc.com/mods/universal-venue-list/`).
4. **Basemental Eco Hacks & Bust The Dust Tweaks**.

---

## 3. Interception Prioritaire des Dépendances (`SPECIAL_DEPENDENCY_CASES`)

Toute dépendance nommée `Basemental Drugs`, `Basemental Drug`, `Basemental Gangs` ou `Universal Venue List` est automatiquement résolue vers `basementalcc.com`.

---

## 4. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](../../tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_multi_platform_dependencies_and_dedup.py`](../../tests/unit/application/test_multi_platform_dependencies_and_dedup.py)

