"""Registre modulaire et moteur de découverte de plugins pour les fournisseurs de mods."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable, Dict, List, Optional, Type

from src.providers.base import BaseSourceProvider
from src.utils.logger import logger



class ProviderRegistry:
    """Registre dynamique et extensible pour les fournisseurs de mods (LoversLab, Patreon, plugins tiers)."""

    _providers: Dict[str, BaseSourceProvider] = {}
    _provider_classes: Dict[str, Type[BaseSourceProvider]] = {}
    _is_initialized: bool = False

    @classmethod
    def register_provider(cls, name: str) -> Callable[[Type[BaseSourceProvider]], Type[BaseSourceProvider]]:
        """Décorateur de classe permettant d'enregistrer un plugin de fournisseur.

        Exemple:
            @ProviderRegistry.register_provider("curseforge")
            class CurseForgeProvider(BaseSourceProvider):
                ...
        """

        def decorator(provider_cls: Type[BaseSourceProvider]) -> Type[BaseSourceProvider]:
            key = name.lower()
            cls._provider_classes[key] = provider_cls
            # Si le registre est déjà initialisé, instancier immédiatement
            if cls._is_initialized and key not in cls._providers:
                try:
                    cls._providers[key] = provider_cls()
                    logger.info(f"Plugin fournisseur '{name}' enregistré dynamiquement.")
                except Exception as e:
                    logger.error(f"Erreur lors de l'instanciation du plugin '{name}': {e}")
            return provider_cls

        return decorator

    @classmethod
    def register(cls, provider: BaseSourceProvider, name: Optional[str] = None) -> None:
        """Enregistre manuellement une instance de fournisseur."""
        key = (name or provider.provider_name).lower()
        cls._providers[key] = provider
        logger.info(f"Fournisseur '{key}' enregistré manuellement.")

    @classmethod
    def discover_plugins(cls, plugins_dir: Optional[Path] = None) -> List[str]:
        """Découvre et charge automatiquement les plugins Python présents dans le dossier plugins/."""
        target_dir = plugins_dir or (Path(__file__).resolve().parents[2] / "plugins")
        if not target_dir.exists() or not target_dir.is_dir():
            return []

        loaded_plugins: List[str] = []
        for file_path in target_dir.glob("*.py"):
            if file_path.name.startswith(("_", ".")):
                continue

            plugin_name = file_path.stem
            try:
                spec = importlib.util.spec_from_file_location(f"plugins.{plugin_name}", file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    loaded_plugins.append(plugin_name)
                    logger.info(f"Plugin externe '{plugin_name}' chargé avec succès depuis {file_path.name}.")
            except Exception as e:
                logger.error(f"Erreur lors du chargement du plugin '{plugin_name}': {e}")

        return loaded_plugins

    @classmethod
    def initialize(cls) -> None:
        """Initialise le registre en chargeant les plugins natifs et externes."""
        if cls._is_initialized:
            return

        # 1. Importer les modules de plugins natifs (qui s'auto-enregistrent via décorateur)
        try:
            import src.providers.loverslab  # noqa: F401
        except Exception as e:
            logger.warning(f"Impossible de charger le plugin LoversLab: {e}")

        try:
            import src.providers.patreon  # noqa: F401
        except Exception as e:
            logger.warning(f"Impossible de charger le plugin Patreon: {e}")

        # 2. Instancier chaque classe enregistrée
        for key, p_cls in cls._provider_classes.items():
            if key not in cls._providers:
                try:
                    cls._providers[key] = p_cls()
                except Exception as e:
                    logger.error(f"Erreur lors de l'instanciation de '{key}': {e}")

        cls._is_initialized = True

        # 3. Découverte des plugins tiers du dossier plugins/
        cls.discover_plugins()

    @classmethod
    def get_provider(cls, name: str) -> Optional[BaseSourceProvider]:
        """Retourne le fournisseur correspondant au nom ou None si introuvable."""
        if not cls._is_initialized:
            cls.initialize()
        return cls._providers.get(name.lower())

    @classmethod
    def list_providers(cls) -> List[BaseSourceProvider]:
        """Retourne la liste de toutes les instances de fournisseurs enregistrées."""
        if not cls._is_initialized:
            cls.initialize()
        return list(cls._providers.values())
