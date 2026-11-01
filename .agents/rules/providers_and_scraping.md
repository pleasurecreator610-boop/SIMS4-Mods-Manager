# Fournisseurs de Mods (22 Plateformes) & Intégrations de Scraping

## 1. Architecture à 2 Socles Mutualisés (`src/providers/common/`)
Tous les plugins dans `plugins/<provider>/` sont découverts automatiquement par `ProviderRegistry` via `@register_provider` et s'appuient sur :
1. **`BaseIPSForumProvider` (`src/providers/common/ips_base.py`)** :
   - Mutualise les forums Invision Community (IPS4) : `loverslab` et `nsfwmods`.
2. **`BasePortalProvider` (`src/providers/common/portal_base.py`)** :
   - Mutualise les **5 portails officiels de frameworks** (`deaderpool`, `scumbumbo`, `lumpinou`, `wickedcc`, `basemental`), les **6 catalogues & portails créateurs SFW** (`gamebanana`, `thesimscatalog`, `itchio`, `sims4studio`, `littlemssam`, `sixamcc`) et les **3 portails adultes `+18`** (`synthira`, `f95zone`, `smutbase`).
3. **Providers Spécialisés** : `curseforge`, `thesimsresource`, `modthesims`, `nexusmods`, `patreon`, `simsfinds`, `mmccworld`, `simfileshare`.

---

## 2. Séparation Comptes Requis vs Sites Publics Sans Compte
- **`PUBLIC_NO_ACCOUNT_PROVIDERS`** (`deaderpool`, `scumbumbo`, `lumpinou`, `wickedcc`, `basemental`, `thesimscatalog`, `littlemssam`, `sixamcc`, `smutbase`) :
  - Sites 100% publics en téléchargement direct. Ils ne doivent **jamais** afficher de carte de connexion inutile dans `AccountsView`.
- **`ACCOUNT_SUPPORTED_PROVIDERS`** (`loverslab`, `nsfwmods`, `curseforge`, `thesimsresource`, `patreon`, `modthesims`, `simsfinds`, `nexusmods`, `simfileshare`, `mmccworld`, `sims4studio`, `f95zone`, `itchio`, `gamebanana`, `synthira`) :
  - Disposent d'une carte dans `AccountsView` (avec masquage automatique des cartes `+18` lorsque `adult_content_enabled` est désactivé).

---

## 3. Téléchargement & Rejet Strict des Pages HTML
- Tout appel à `download_mod_file` doit vérifier l'en-tête `Content-Type` et les premiers octets du flux binaire.
- Si le serveur renvoie `text/html`, `<!doctype html` ou `<html` (page de connexion ou défi Cloudflare), le téléchargement doit retourner `(False, message_explicite)` sans jamais écrire un fichier `.zip` ou `.package` corrompu.
