# Fournisseurs Maxis Match CC World (`mmccworld`) & SimFileShare (`simfileshare`)

Ces deux fournisseurs complémentaires couvrent l'écosystème Tumblr / SimFileShare de la communauté **Les Sims 4**.

---

## 1. Maxis Match CC World (`mmccworld`)

- **Classe d'Implémentation** : [`plugins/mmccworld/provider.py`](../../plugins/mmccworld/provider.py) (`MMCCWorldProvider`)
- **URL Officielle** : `https://maxismatchccworld.tumblr.com`
- **Contenu Adulte (`+18`)** : Non (`SFW`)
- **Compte Utilisateur** : Optionnel (`ACCOUNT_SUPPORTED_PROVIDERS` via Tumblr) — permet d'envoyer des messages/Asks aux créateurs.
- **Fonctionnement** : Parcourt les catégories CAS, Build/Buy et Gameplay et résout automatiquement les liens externes vers SimFileShare, Patreon ou CurseForge.

---

## 2. Résolveur Universel SimFileShare (`simfileshare`)

- **Classe d'Implémentation** : [`plugins/simfileshare/provider.py`](../../plugins/simfileshare/provider.py) (`SimFileShareProvider`)
- **URL Officielle** : `https://simfileshare.net`
- **Compte Utilisateur** : Optionnel (`simfileshare` fonctionne sans compte pour tous les téléchargements directs `/download/{id}/` et les dossiers `/folder/{id}/`).

