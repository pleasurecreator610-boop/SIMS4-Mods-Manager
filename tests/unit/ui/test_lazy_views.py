"""Tests unitaires pour l'instanciation différée (Lazy Loading) des vues Qt dans MainWindow."""

import pytest

from src.ui.app import MainWindow
from src.ui.views.accounts_view import AccountsView
from src.ui.views.catalog_view import CatalogView
from src.ui.views.installed_view import InstalledView
from src.ui.views.downloads_view import DownloadsView
from src.ui.views.updates_view import UpdatesView
from src.ui.views.logs_view import LogsView
from src.ui.views.settings_view import SettingsView
from src.ui.views.mod_detail_view import ModDetailView


@pytest.fixture(autouse=True)
def mock_subview_network_calls(monkeypatch):
    """Évite les requêtes HTTP en arrière-plan pendant l'instanciation des vues en test unitaire."""
    monkeypatch.setattr(CatalogView, "_check_sync_status", lambda self: None)
    monkeypatch.setattr(CatalogView, "refresh_catalog", lambda self, *a, **k: None)
    monkeypatch.setattr(InstalledView, "refresh_mods", lambda self, *a, **k: None)
    monkeypatch.setattr(AccountsView, "refresh_statuses", lambda self: None)


def test_main_window_lazy_loading_single_view_on_init(qapp, monkeypatch):
    """Vérifie qu'au démarrage, seule la vue initiale est instanciée (pas les 8)."""
    monkeypatch.setattr(MainWindow, "refresh_game_status", lambda self: None)
    monkeypatch.setattr(MainWindow, "update_nav_badge", lambda self: None)
    monkeypatch.setattr(MainWindow, "auto_start_background_sync", lambda self: None)
    monkeypatch.setattr(MainWindow, "_has_configured_account", lambda self: False)

    win = MainWindow()
    try:
        # Quand aucun compte n'est configuré, seule la vue Accounts (index 0) doit être instanciée
        assert 0 in win._views
        assert len(win._views) == 1
        assert isinstance(win._views[0], AccountsView)
        assert 1 not in win._views
        assert 2 not in win._views
        assert 7 not in win._views

        # Lors du switch_page vers Installed (index 2), celle-ci est créée à la demande
        win.switch_page(2)
        assert 2 in win._views
        assert isinstance(win._views[2], InstalledView)
        assert len(win._views) == 2

        # L'accès via property instancie la vue demandée si pas encore présente
        detail = win.mod_detail_view
        assert isinstance(detail, ModDetailView)
        assert 7 in win._views
        assert len(win._views) == 3
    finally:
        win.close()


def test_main_window_default_page_with_configured_account(qapp, monkeypatch):
    """Vérifie que la vue Catalogue (index 1) est la page d'accueil si au moins un compte est prêt."""
    monkeypatch.setattr(MainWindow, "refresh_game_status", lambda self: None)
    monkeypatch.setattr(MainWindow, "update_nav_badge", lambda self: None)
    monkeypatch.setattr(MainWindow, "auto_start_background_sync", lambda self: None)
    monkeypatch.setattr(MainWindow, "_has_configured_account", lambda self: True)

    win = MainWindow()
    try:
        # Avec compte configuré, CatalogView (index 1) est sélectionnée
        assert win.stacked_widget.currentIndex() == 1
        assert 1 in win._views
        assert isinstance(win._views[1], CatalogView)
        assert 0 not in win._views
    finally:
        win.close()


def test_main_window_all_lazy_properties(qapp, monkeypatch):
    """Vérifie que toutes les properties de vues retournent les bonnes classes."""
    monkeypatch.setattr(MainWindow, "refresh_game_status", lambda self: None)
    monkeypatch.setattr(MainWindow, "update_nav_badge", lambda self: None)
    monkeypatch.setattr(MainWindow, "auto_start_background_sync", lambda self: None)

    win = MainWindow()
    try:
        assert isinstance(win.accounts_view, AccountsView)
        assert isinstance(win.catalog_view, CatalogView)
        assert isinstance(win.installed_view, InstalledView)
        assert isinstance(win.downloads_view, DownloadsView)
        assert isinstance(win.updates_view, UpdatesView)
        assert isinstance(win.logs_view, LogsView)
        assert isinstance(win.settings_view, SettingsView)
        assert isinstance(win.mod_detail_view, ModDetailView)
        assert len(win._views) == 8
    finally:
        win.close()
