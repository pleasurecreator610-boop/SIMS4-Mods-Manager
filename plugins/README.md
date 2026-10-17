# Dossier des Plugins de Fournisseurs de Mods (Plugins Directory)

Ce dossier permet d'ajouter dynamiquement de nouvelles sources de téléchargement et d'indexation de mods (ex. **CurseForge**, **NexusMods**, **ModTheSims**...) sans modifier le code source de l'application.

---

## 🚀 Comment créer un plugin ?

1. Créez un fichier Python dans ce dossier (ex: `curseforge_plugin.py`).
2. Héritez de `BaseSourceProvider` et ajoutez le décorateur `@ProviderRegistry.register_provider("nom_du_provider")`.
3. Implémentez les méthodes requises (`scrape_catalog`, `get_mod_details`, `download_mod_file`, `check_access`).

### Exemple Minimal :

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
        # Votre logique de scraping ou d'appel API REST
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

Au lancement de l'application (ou de l'API), le plugin est **découvert et enregistré automatiquement** !
