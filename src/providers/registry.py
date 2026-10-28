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
        """Découvre et charge automatiquement les plugins Python (packages ou scripts) présents dans plugins/."""
        import sys

        target_dir = plugins_dir or (Path(__file__).resolve().parents[2] / "plugins")
        if not target_dir.exists() or not target_dir.is_dir():
            return []

        loaded_plugins: List[str] = []

        # 1. Découvrir les dossiers de plugins (packages avec __init__.py)
        for sub_dir in sorted(target_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith(("_", ".")):
                continue
            init_file = sub_dir / "__init__.py"
            if init_file.exists():
                plugin_name = sub_dir.name
                try:
                    spec = importlib.util.spec_from_file_location(f"plugins.{plugin_name}", init_file)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[f"plugins.{plugin_name}"] = module
                        spec.loader.exec_module(module)
                        loaded_plugins.append(plugin_name)
                        logger.info(f"Plugin package '{plugin_name}' chargé avec succès depuis {sub_dir.name}/.")
                except Exception as e:
                    logger.error(f"Erreur lors du chargement du package plugin '{plugin_name}': {e}")

        # 2. Découvrir les plugins isolés (*.py)
        for file_path in sorted(target_dir.glob("*.py")):
            if file_path.name.startswith(("_", ".")):
                continue

            plugin_name = file_path.stem
            if plugin_name in loaded_plugins:
                continue

            try:
                spec = importlib.util.spec_from_file_location(f"plugins.{plugin_name}", file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"plugins.{plugin_name}"] = module
                    spec.loader.exec_module(module)
                    loaded_plugins.append(plugin_name)
                    logger.info(f"Plugin fichier '{plugin_name}' chargé avec succès depuis {file_path.name}.")
            except Exception as e:
                logger.error(f"Erreur lors du chargement du plugin fichier '{plugin_name}': {e}")

        # Instancier les classes enregistrées
        for key, p_cls in cls._provider_classes.items():
            if key not in cls._providers:
                try:
                    cls._providers[key] = p_cls()
                except Exception as e:
                    logger.error(f"Erreur lors de l'instanciation de '{key}': {e}")

        return loaded_plugins

    @classmethod
    def initialize(cls) -> None:
        """Initialise le registre en chargeant les plugins du dossier plugins/."""
        if cls._is_initialized:
            return

        cls.discover_plugins()
        cls._is_initialized = True

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
