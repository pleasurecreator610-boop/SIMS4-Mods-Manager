# Directives de Tests Unitaires & Validation Par Provider (Green State)

## 1. Règle de Validation Obligatoire (Green State)
Avant chaque commit ou fusion de Pull Request, les vérifications suivantes doivent passer à 100% (0 erreur, 0 warning) :

```powershell
# 1. Audit de conformité statique complet (Ruff, Bandit, Vulture, Deptry, Mypy)
python D:\Workspace\Gitlab\workspace\02_compliance_code\python\analyze.py --target . --skip-update

# 2. Exécution des tests ÉLÉMENT PAR ÉLÉMENT en terminal visible (-v)
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

---

## 2. Les 7 Familles de Tests Obligatoires pour Chaque Provider

Tout nouveau provider dans `plugins/<provider>/` doit obligatoirement être couvert par les 7 familles de tests suivantes :
1. **Découverte `ProviderRegistry` & Classification** (`ADULT_PROVIDERS`, `ACCOUNT_SUPPORTED_PROVIDERS` vs `PUBLIC_NO_ACCOUNT_PROVIDERS`, `CATEGORIES`).
2. **Scraping de Catégorie & Détails de Mod** (`scrape_category_page`, `get_mod_details`, extraction des liens et prérequis).
3. **Téléchargement Binaire vs Rejet HTML** (`download_mod_file` : acceptation des archives `.zip`/`.package` et rejet des pages HTML/Cloudflare/login walls).
4. **Installation Multi-Mods avec Dépendances Multiples (Même Plateforme & Inter-Plateformes)** : redirection prioritaire vers les sites officiels (`deaderpool`, `scumbumbo`, `lumpinou`, `wickedcc`, `basemental`, `sims4studio`) et déduplication concurrente via `ActiveInstallationRegistry`.
5. **Installation d'un Même Mod entre Plusieurs Plateformes** : reconnaissance par `ModMatcher.canonical_fingerprint` et statut `INSTALLED` sans re-téléchargement ni collision.
6. **Classification `MOD` vs `COMMENT_NOISE` & Bascule Manuelle (`MOD` $\leftrightarrow$ `COMMENT`)** via `requirements_overrides`.
7. **Signalement & Commentaires aux Créateurs (`RequirementReporterService`)** : refus explicite avec demande d'authentification si `is_member_authenticated == False`, puis vérification anti-doublon, publication (commentaire & MP) et suppression une fois authentifié.

---

## 3. Règles Critiques d'Exécution & Isolation BDD
- **Exécution par Module (`-v`)** : Ne jamais lancer `pytest` globalement en un seul bloc ni en tâche de fond silencieuse.
- **Zéro Appel Réseau Réel** : Tous les appels HTTP doivent être mockés (`monkeypatch` sur `SessionManager.get_http_session`).
- **Isolation SQLite** : `tests/conftest.py` isole automatiquement `SIMS4_DB_PATH` dans un dossier temporaire par session de test.
