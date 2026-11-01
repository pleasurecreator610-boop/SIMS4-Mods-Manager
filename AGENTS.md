# Guide Normalisé & Directives Impératives pour Agents LLM (`AGENTS.md`)

> Ce document définit le contrat d'architecture, les règles de résolution de dépendances officielles et la **matrice normalisée des 7 familles de tests obligatoires** pour tout fournisseur (provider) de mods dans **SIMS 4 Mods Manager**.

---

## 1. Architecture & Contrat d'Implémentation d'un Provider

Tout provider est un plugin auto-découvert dans `plugins/<provider_name>/` décoré par `@register_provider` et héritant de `BaseSourceProvider` (ou des socles mutualisés `BasePortalProvider` / `BaseIPSForumProvider`).

### 1.1 Checklist d'Intégration d'une Nouvelle Plateforme
1. **Plugin (`plugins/<provider>/provider.py` & `__init__.py`)** :
   - Définir `provider_name`, `display_name`, `base_url`, `CATEGORIES` (`List[Dict[str, Any]]`).
   - Implémenter `scrape_category_page(category, page, limit)`, `get_mod_details(mod_url)`, `download_mod_file(download_url, dest_path, progress_callback)`, `check_access(mod_data)`.
   - Si la plateforme supporte les commentaires/MP, implémenter `get_creator_info`, `check_user_already_commented`, `post_mod_comment`, `delete_mod_comment` et `send_private_message`.
2. **Configuration & Classification (`src/core/config.py`)** :
   - Ajouter dans `ADULT_PROVIDERS` si le site est `+18`.
   - Ajouter dans `ACCOUNT_SUPPORTED_PROVIDERS` (si compte/session utile) ou dans `PUBLIC_NO_ACCOUNT_PROVIDERS` (si site 100% public sans compte).
3. **Suivi & API (`src/application/catalog/sync_tracker.py` & `src/api/routes/accounts_router.py`)** :
   - Déclarer l'état initial dans `SyncTracker.providers_status` et `SyncTracker.reset()`.
   - Ajouter l'URL de login dans `accounts_router.py` et la vérification live dans `SessionManager.verify_session()` si le site supporte les comptes.
4. **Interface Utilisateur (`src/ui/`)** :
   - `filter_bar.py` & `filter_adapter.py` (filtre par source et masquage `+18`).
   - `status_badge.py` (badge visuel distinct).
   - `provider_drawer/provider_scraper_card.py` & `drawer.py` (pilule latérale et carte de progression).
   - `accounts_view.py` & `src/i18n/locales/{fr,en}.json` (uniquement si le provider est dans `ACCOUNT_SUPPORTED_PROVIDERS`).
5. **Documentation (`documentation/providers/<provider>.md` & `mkdocs.yml`)** :
   - Créer la fiche technique complète du provider et l'indexer dans `mkdocs.yml`.

---

## 2. Règle Impérative : Priorité Absolue aux Sites Officiels des Frameworks

Les frameworks suivants doivent **TOUJOURS** être résolus et téléchargés depuis leurs sites officiels publics via [`src/application/dependencies/dependency_special_cases.py`](./src/application/dependencies/dependency_special_cases.py), même lorsqu'un mod pointe vers un lien tiers (LoversLab, CurseForge, ModTheSims, Patreon) :

- **Deaderpool (`deaderpool`)** : *MC Command Center (MCCC)* & *MC WooHoo* (`https://deaderpool-mccc.com`)
- **Scumbumbo (`scumbumbo`)** : *XML Injector*, *Teleport Any Sim*, etc. (`https://scumbumbomods.com`)
- **Lumpinou (`lumpinou`)** : *RPO (WooHoo Wellness)*, *Mood Pack Mod*, *Lumpinou's Toolbox*, *LGBTQIA+ Mod* (`https://www.lumpinoumods.com`)
- **Wicked.cc (`wickedcc`)** : *WickedWhims* (`3169`) & *WonderfulWhims* (`https://wicked.cc` / `https://wonderfulwhims.com`)
- **Basemental (`basemental`)** : *Basemental Drugs*, *Basemental Gangs*, *Universal Venue List* (`https://basementalcc.com`)
- **Sims 4 Studio (`sims4studio`)** : *Andrew's Pose Player* (`https://sims4studio.com/thread/2617/andrews-studio`)

---

## 3. Les 7 Familles de Tests Unitaires & Intégration Obligatoires par Provider

Tout ajout ou modification d'un provider par un agent LLM **DOIT** être accompagné des 7 familles de tests suivantes (100% mockées, zéro appel réseau réel) :

| # | Famille de Test | Ce qui doit être vérifié par les assertions | Fichier de Test de Référence |
| :--- | :--- | :--- | :--- |
| **1** | **Enregistrement & Découverte (`ProviderRegistry`)** | Découverte dynamique du plugin, présence de `CATEGORIES` non vide, classification exacte dans `ADULT_PROVIDERS`, `ACCOUNT_SUPPORTED_PROVIDERS` ou `PUBLIC_NO_ACCOUNT_PROVIDERS`. | `tests/unit/providers/test_new_platforms_providers.py` |
| **2** | **Scraping Catalogue & Fiche Détail (`scrape_category_page` & `get_mod_details`)** | Parsing HTML/JSON des listes paginées, extraction du titre, auteur, miniature, `download_urls` et `requirements_mods`, plus repli gracieux en cas d'erreur HTTP. | `tests/unit/providers/test_new_platforms_providers.py` |
| **3** | **Téléchargement & Rejet des Murs HTML (`download_mod_file`)** | Validation d'une archive binaire (`.zip` / `.package`) écrite sur disque (`(True, path)`) ET rejet explicite (`(False, err)`) lorsqu'une page HTML (`<!DOCTYPE html>`, Cloudflare ou login wall) est retournée. | `tests/unit/providers/test_new_platforms_providers.py` |
| **4** | **Dépendances Multiples Même Plateforme & Inter-Plateformes** | Lors de l'installation simultanée de plusieurs mods ayant plusieurs dépendances (de la même plateforme et d'autres plateformes) : redirection prioritaire vers `deaderpool`, `scumbumbo`, `lumpinou`, `wickedcc`, `basemental`, et déduplication concurrente via `ActiveInstallationRegistry`. | `tests/unit/application/test_multi_platform_dependencies_and_dedup.py` |
| **5** | **Installation d'un Même Mod entre Plusieurs Plateformes** | Empreinte canonique (`ModMatcher.canonical_fingerprint`) identique indépendamment de la plateforme ou du suffixe de version ; statut résolu en `INSTALLED` sans re-téléchargement ni collision de dossier. | `tests/unit/application/test_multi_platform_dependencies_and_dedup.py` |
| **6** | **Classification `MOD` vs `COMMENT_NOISE` & Surcharge Utilisateur** | Filtrage automatique des notes/consignes d'auteurs en `COMMENT_NOISE`, conservation des vrais mods, et bascule manuelle bidirectionnelle `MOD` $\leftrightarrow$ `COMMENT` via `requirements_overrides`. | `tests/unit/application/test_new_platforms_reporting_and_comments.py` |
| **7** | **Authentification & Envoi de Commentaire / MP au Créateur** | Sur les plateformes supportant les comptes : blocage avec invitation à se connecter lorsque `SessionManager.is_member_authenticated(source) == False`, puis après authentification : vérification anti-doublon (`check_report_status`), publication (`submit_report` commentaire & MP) et suppression (`delete_report`). | `tests/unit/application/test_new_platforms_reporting_and_comments.py` |

---

## 4. Protocole d'Exécution des Tests & Conformité Statique

1. **Exécution par Module en Terminal Visible (`-v`)** :
   Ne jamais lancer `pytest` sur tout le dépôt en une seule commande bloquante. Toujours exécuter module par module :
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/unit/core -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/utils -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/database -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/domain -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/infrastructure -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/security -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/providers -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/application -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/api -v
   .\.venv\Scripts\python.exe -m pytest tests/unit/ui -v
   .\.venv\Scripts\python.exe -m pytest tests/e2e -v
   ```
2. **Audit Statique (`02_compliance_code/python`)** :
   ```powershell
   python D:\Workspace\Gitlab\workspace\02_compliance_code\python\analyze.py --target . --skip-update
   ```
   Doit retourner **0 erreur et 0 avertissement** (Ruff, Bandit, Vulture, Deptry, Mypy).

