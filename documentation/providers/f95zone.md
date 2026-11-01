# Fournisseur F95zone (`f95zone` • `+18`)

Le fournisseur `f95zone` intègre les fils dédiés aux mods, scripts et compilations d'animations **The Sims 4** sur le forum XenForo **F95zone** (`f95zone.to`).

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `f95zone`
- **Classe d'Implémentation** : [`plugins/f95zone/provider.py`](../../plugins/f95zone/provider.py) (`F95ZoneProvider`)
- **URL Officielle** : `https://f95zone.to`
- **Contenu Adulte (`+18`)** : Oui (`ADULT_PROVIDERS`)
- **Compte Utilisateur** : Supporté (`ACCOUNT_SUPPORTED_PROVIDERS`) — la connexion XenForo permet de déverrouiller les liens spoilers/téléchargements réservés aux membres et de poster des messages sur les fils de discussion ou par conversation privée (`/conversations/add?to=`).

---

## 2. Catégories Prises en Charge

- **Sims 4 Mods & Animation Packs (`f95_sims4_mods`)**
- **Sims 4 Scripts & Gameplay Overhauls (`f95_sims4_scripts`)**

---

## 3. Tests Automatisés Associés

- [`tests/unit/providers/test_new_platforms_providers.py`](../../tests/unit/providers/test_new_platforms_providers.py)
- [`tests/unit/application/test_new_platforms_reporting_and_comments.py`](../../tests/unit/application/test_new_platforms_reporting_and_comments.py)

