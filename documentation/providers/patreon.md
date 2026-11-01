# Fournisseur Patreon (`patreon`)

Le fournisseur `patreon` permet d'indexer, vérifier les droits d'abonnement et télécharger les pièces jointes de mods **Les Sims 4** hébergés sur **Patreon** (`patreon.com`).

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `patreon`
- **Classe d'Implémentation** : [`plugins/patreon/provider.py`](../../plugins/patreon/provider.py) (`PatreonProvider`)
- **URL Officielle** : `https://www.patreon.com`
- **Contenu Adulte (`+18`)** : Non (`SFW` par défaut)
- **Compte Utilisateur** : Optionnel (`ACCOUNT_SUPPORTED_PROVIDERS`) — permet de débloquer les publications réservées aux abonnés (`UNLOCKED` vs `LOCKED`) et de publier des commentaires.
- **Filtrage des Pièces Jointes** : Écarte automatiquement les simples images (`.png`, `.jpg`) pour ne télécharger que les archives et fichiers `.package` / `.ts4script`.

