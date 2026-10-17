# Moteur et Dossier des Plugins de Fournisseurs (Plugins Directory)

Ce dossier héberge l'ensemble des modules fournisseurs de mods sous forme de **plugins modulaires et découvrables dynamiquement**.
Il contient à la fois les fournisseurs intégrés officiels (**LoversLab**, **Patreon**) et permet d'ajouter de nouvelles sources externes (**CurseForge**, **NexusMods**, **ModTheSims**...) sans modifier le noyau `src/`.

---

## 📁 Architecture des Plugins

Le moteur de découverte `ProviderRegistry.discover_plugins()` supporte deux formats de plugins :

1. **Packages Modulaires Multi-fichiers** (recommandé pour les fournisseurs complexes) :
   - Exemple : `plugins/loverslab/` ou `plugins/patreon/`
   - Structure :
     ```text
     plugins/
     ├── loverslab/
     │   ├── __init__.py                # Point d'entrée avec export et décorateur @register_provider
     │   ├── scraper.py                 # Implémentation principale héritant de BaseSourceProvider
     │   ├── downloader.py              # Téléchargement asynchrone / streaming
     │   ├── forum_service.py           # Publication de commentaires et interpellation d'auteurs
     │   ├── page_parser.py             # Analyse HTML des pages du catalogue
     │   ├── parsers.py                 # Extraction de métadonnées et galeries
     │   ├── matchers.py                # Détection et classification de noms de mods
     │   └── requirements_extractor.py  # Analyseur de dépendances et prérequis
     ├── patreon/
     │   ├── __init__.py                # Export du provider Patreon
     │   └── provider.py                # Gestion des posts, tiers, pledge access et téléchargements
     ```
2. **Scripts Python Monofichiers** :
   - Exemple : `plugins/curseforge_plugin.py`

---

## 🚀 Comment créer un nouveau Plugin ?

### Option A : Plugin Script Simple (`plugins/mon_site.py`)

```python
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.core.dto import ModDetailsDTO
from src.providers.base import BaseSourceProvider
from src.providers.registry import ProviderRegistry


@ProviderRegistry.register_provider("mon_site")
class MonSiteProvider(BaseSourceProvider):
    provider_name = "mon_site"
    display_name = "Mon Site de Mods"
    base_url = "https://www.monsite.com"

    def scrape_catalog(self, page: int = 1, limit: int = 25) -> List[Dict[str, Any]]:
        return []

    def get_mod_details(self, mod_url: str) -> Union[Dict[str, Any], ModDetailsDTO]:
        return {}

    def download_mod_file(
        self,
        download_url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> Tuple[bool, str]:
        return False, "Non implémenté"

    def check_access(self, mod_data: Dict[str, Any]) -> str:
        return "PUBLIC"

    def check_user_already_commented(self, page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        return False, None

    def post_mod_comment(self, page_url: str, message: str) -> Tuple[bool, str]:
        return False, "Commentaires non supportés"
```

### Option B : Package Plugin Structuré (`plugins/mon_site/`)

1. Créez le dossier `plugins/mon_site/`.
2. Créez `__init__.py` important votre classe provider et exportant les fonctions utilitaires nécessaires.
3. Décorez la classe avec `@ProviderRegistry.register_provider("mon_site")`.

Au lancement de l'application ou de l'API REST, `ProviderRegistry.initialize()` charge automatiquement tous les packages et fichiers Python présents dans `plugins/` !
