from PySide6.QtCore import QTimer, QObject, Signal, QRunnable, QThreadPool
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QFrame,
    QMessageBox,
)

from src.api.client import get_api_client
from src.core.config import AppConfig
from src.core.shutdown_manager import ShutdownManager
from src.i18n import I18nManager, tr
from src.ui.theme import DARK_THEME_QSS
from src.ui.components.sidebar_nav import SidebarNavWidget
from src.ui.views.accounts_view import AccountsView
from src.ui.views.catalog_view import CatalogView
from src.ui.views.installed_view import InstalledView
from src.ui.views.downloads_view import DownloadsView
from src.ui.views.logs_view import LogsView
from src.ui.views.mod_detail_view import ModDetailView
from src.ui.views.settings_view import SettingsView
from src.ui.views.updates_view import UpdatesView
from src.utils.logger import logger
from src.utils.thread_utils import cleanup_all_threads


class StatusCheckSignals(QObject):
    """Classe StatusCheckSignals : assure la gestion et l'orchestration de Statuschecksignals."""

    health_checked = Signal(bool, bool)  # success, mods_detected
    updates_checked = Signal(int)  # updates_count


class BackgroundStatusWorker(QRunnable):
    """Executes lightweight health and updates checks off the Qt GUI thread."""

    def __init__(self, api_client, signals: StatusCheckSignals):
        super().__init__()
        self.api_client = api_client
        self.signals = signals
        self.setAutoDelete(False)

    def run(self):
        """Exécute l'opération run."""
        try:
            health = self.api_client.get_health()
            self.signals.health_checked.emit(True, health.get("mods_dir_detected", False))
        except Exception:
            self.signals.health_checked.emit(False, False)

        try:
            data = self.api_client.get_updates()
            self.signals.updates_checked.emit(data.get("count", 0))
        except Exception:
            self.signals.updates_checked.emit(0)


class MainWindow(QMainWindow):
    """Main application window for SIMS 4 Mods Manager connected 100% via REST API."""

    def __init__(self):
        super().__init__()
        self.api_client = get_api_client()
        self.i18n = I18nManager.instance()
        self.status_signals = StatusCheckSignals()
        self.status_signals.health_checked.connect(self._on_health_checked)
        self.status_signals.updates_checked.connect(self._on_updates_checked)

        initial_lang = AppConfig.load().language
        self.i18n.set_language(initial_lang)

        self.setWindowTitle(tr("app.window_title"))
        self.resize(1280, 800)
        self.setMinimumSize(1000, 650)
        self.setStyleSheet(DARK_THEME_QSS)

        self.init_ui()
        self.i18n.language_changed.connect(self.retranslate_ui)
        self.refresh_game_status()
        self.update_nav_badge()

        QTimer.singleShot(10000, self.auto_start_background_sync)

    def init_ui(self):
        """Exécute l'opération init ui."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar = SidebarNavWidget(self)
        self.sidebar.page_requested.connect(self.switch_page)
        self.sidebar.launch_game_requested.connect(self._launch_game)
        main_layout.addWidget(self.sidebar)

        # 2. Right Content Stacked Pages
        content_area = QFrame()
        content_area.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()
        self._views: dict[int, QWidget] = {}

        # 8 placeholders pour préserver l'indexation stricte 0 à 7
        for _ in range(8):
            self.stacked_widget.addWidget(QWidget())

        content_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(content_area)

        # Décision de la vue d'accueil : Catalogue si au moins 1 compte configuré, sinon Comptes
        initial_page = 1 if self._has_configured_account() else 0
        self.current_origin_index = initial_page
        self.switch_page(initial_page)

    def _has_configured_account(self) -> bool:
        """Détecte si au moins un compte ou fournisseur externe est configuré ou validé."""
        try:
            from src.core.session_manager import SessionManager

            cfg = AppConfig.load()
            if getattr(cfg, "nexusmods_api_key", None):
                return True

            providers = (
                "curseforge",
                "thesimsresource",
                "modthesims",
                "loverslab",
                "nsfwmods",
                "patreon",
                "nexusmods",
                "simsfinds",
                "mmccworld",
            )
            for p in providers:
                if SessionManager.is_session_ready(p) or SessionManager.is_member_authenticated(p):
                    return True
        except Exception as e:
            logger.debug(f"Erreur détection compte configuré: {e}")
        return False

    def _create_view(self, index: int) -> QWidget:
        """Instancie et configure une vue de manière différée (Lazy Loading)."""
        if index == 0:
            view = AccountsView()
            view.login_successful.connect(self._on_login_success)
            view.adult_content_toggled.connect(self._on_adult_content_changed)
            return view
        elif index == 1:
            view = CatalogView()
            view.details_requested.connect(lambda d: self.show_mod_details(d, origin_name="Catalogue", origin_index=1))
            view.download_requested.connect(lambda d: self.downloads_view.start_download(d))
            view.view_downloads_requested.connect(lambda: self.switch_page(3))
            view.install_finished.connect(self._on_mods_state_changed)
            view.adult_content_changed.connect(self._on_adult_content_changed)
            return view
        elif index == 2:
            view = InstalledView()
            view.details_requested.connect(lambda d: self.show_mod_details(d, origin_name="Mes Mods", origin_index=2))
            view.mods_changed.connect(self._on_mods_state_changed)
            return view
        elif index == 3:
            view = DownloadsView()
            view.details_requested.connect(
                lambda d: self.show_mod_details(d, origin_name="Téléchargements", origin_index=3)
            )
            view.open_folder_requested.connect(lambda p: self.installed_view.open_mod_folder(p))
            view.active_count_changed.connect(self.sidebar.update_downloads_badge)
            view.install_finished.connect(self._on_mods_state_changed)
            view.install_finished.connect(
                lambda ok, msg: self._views[1].on_external_install_finished(ok, msg) if 1 in self._views else None
            )
            return view
        elif index == 4:
            view = UpdatesView()
            view.updates_applied.connect(self._on_mods_state_changed)
            return view
        elif index == 5:
            return LogsView()
        elif index == 6:
            view = SettingsView()
            view.adult_content_changed.connect(self._on_adult_content_changed)
            return view
        elif index == 7:
            view = ModDetailView()
            view.back_requested.connect(self._on_detail_back)
            view.install_requested.connect(self._on_detail_install_requested)
            view.open_folder_requested.connect(lambda p: self.installed_view.open_mod_folder(p))
            return view
        raise ValueError(f"Index de vue inconnu : {index}")

    def _get_or_create_view(self, index: int) -> QWidget:
        """Récupère une vue existante ou l'instancie si accédée pour la première fois."""
        if index not in self._views:
            view = self._create_view(index)
            self._views[index] = view
            old_w = self.stacked_widget.widget(index)
            self.stacked_widget.insertWidget(index, view)
            if old_w:
                self.stacked_widget.removeWidget(old_w)
                old_w.deleteLater()
        return self._views[index]

    @property
    def accounts_view(self) -> AccountsView:
        return self._get_or_create_view(0)  # type: ignore

    @property
    def catalog_view(self) -> CatalogView:
        return self._get_or_create_view(1)  # type: ignore

    @property
    def installed_view(self) -> InstalledView:
        return self._get_or_create_view(2)  # type: ignore

    @property
    def downloads_view(self) -> DownloadsView:
        return self._get_or_create_view(3)  # type: ignore

    @property
    def updates_view(self) -> UpdatesView:
        return self._get_or_create_view(4)  # type: ignore

    @property
    def logs_view(self) -> LogsView:
        return self._get_or_create_view(5)  # type: ignore

    @property
    def settings_view(self) -> SettingsView:
        return self._get_or_create_view(6)  # type: ignore

    @property
    def mod_detail_view(self) -> ModDetailView:
        return self._get_or_create_view(7)  # type: ignore

    def _on_adult_content_changed(self, enabled: bool):
        """Synchronizes adult content state across all instantiated views immediately."""
        for view in list(self._views.values()):
            if hasattr(view, "set_adult_content_enabled") and callable(view.set_adult_content_enabled):
                try:
                    view.set_adult_content_enabled(enabled)
                except Exception:
                    pass

    # Backward compatible sidebar property accessors
    @property
    def nav_buttons(self):
        """Exécute l'opération nav buttons.

        Returns:
            Résultat de l'opération nav_buttons.
        """
        return self.sidebar.nav_buttons

    @property
    def btn_accounts(self):
        """Exécute l'opération btn accounts.

        Returns:
            Résultat de l'opération btn_accounts.
        """
        return self.sidebar.btn_accounts

    @property
    def btn_catalog(self):
        """Exécute l'opération btn catalog.

        Returns:
            Résultat de l'opération btn_catalog.
        """
        return self.sidebar.btn_catalog

    @property
    def btn_installed(self):
        """Exécute l'opération btn installed.

        Returns:
            Résultat de l'opération btn_installed.
        """
        return self.sidebar.btn_installed

    @property
    def btn_downloads(self):
        """Exécute l'opération btn downloads.

        Returns:
            Résultat de l'opération btn_downloads.
        """
        return self.sidebar.btn_downloads

    @property
    def btn_updates(self):
        """Exécute l'opération btn updates.

        Returns:
            Résultat de l'opération btn_updates.
        """
        return self.sidebar.btn_updates

    @property
    def btn_logs(self):
        """Exécute l'opération btn logs.

        Returns:
            Résultat de l'opération btn_logs.
        """
        return self.sidebar.btn_logs

    @property
    def btn_settings(self):
        """Exécute l'opération btn settings.

        Returns:
            Résultat de l'opération btn_settings.
        """
        return self.sidebar.btn_settings

    @property
    def game_status(self):
        """Exécute l'opération game status.

        Returns:
            Résultat de l'opération game_status.
        """
        return self.sidebar.game_status

    @property
    def play_btn(self):
        """Exécute l'opération play btn.

        Returns:
            Résultat de l'opération play_btn.
        """
        return self.sidebar.play_btn

    def switch_page(self, index: int):
        """Exécute l'opération switch page.

        Args:
            index: Paramètre index.
        """
        self._get_or_create_view(index)
        self.stacked_widget.setCurrentIndex(index)
        self.sidebar.set_active_page(index)

        if index == 0:
            self.accounts_view.refresh_statuses()
        elif index == 1:
            self.catalog_view.refresh_catalog()
        elif index == 2:
            self.installed_view.refresh_mods()
        elif index == 3:
            self.downloads_view.refresh_downloads()
        elif index == 4:
            self.updates_view.refresh_updates()
        elif index == 5:
            self.logs_view.load_initial_history()
        elif index == 6:
            self.settings_view.load_settings()

        self.refresh_game_status()
        self.update_nav_badge()

    def show_mod_details(self, mod_data: dict, origin_name: str = "Catalogue", origin_index: int = 1):
        """Exécute l'opération show mod details.

        Args:
            mod_data: Paramètre mod_data.
            origin_name: Paramètre origin_name.
            origin_index: Paramètre origin_index.
        """
        self.current_origin_index = origin_index
        for btn in self.nav_buttons:
            btn.setChecked(False)
        self.stacked_widget.setCurrentIndex(self.stacked_widget.indexOf(self.mod_detail_view))
        self.mod_detail_view.load_mod(mod_data, origin_name=origin_name, origin_index=origin_index)

    def _on_detail_back(self):
        self.switch_page(self.current_origin_index)

    def _on_detail_install_requested(self, mod_data: dict):
        started = self.catalog_view.install_mod(mod_data)
        if not started and hasattr(self.mod_detail_view, "header_widget"):
            self.mod_detail_view.header_widget.set_installing(False)

    def _on_mods_state_changed(self, *args):
        if 2 in self._views:
            self._views[2].refresh_mods()
        if 4 in self._views:
            self._views[4].refresh_updates()
        if 1 in self._views:
            self._views[1].refresh_catalog()
        self.update_nav_badge()
        if 7 in self._views and self.stacked_widget.currentWidget() == self._views[7]:
            self._refresh_current_mod_detail()

    def _refresh_current_mod_detail(self):
        from src.ui.workers.generic_runnable import run_async_ui_task

        curr_mod = getattr(self.mod_detail_view, "mod_data", None)
        if not curr_mod:
            return

        def _fetch():
            return self.api_client.get_installed_mods()

        def _on_fetched(installed_res):
            try:
                installed_list = installed_res.get("items", []) if isinstance(installed_res, dict) else []
                r_id = str(curr_mod.get("remote_id", ""))
                m_title = curr_mod.get("title", "")
                match = next(
                    (
                        im
                        for im in installed_list
                        if (r_id and str(im.get("remote_id", "")) == r_id) or (m_title and im.get("title") == m_title)
                    ),
                    None,
                )
                updated_data = dict(curr_mod)
                updated_data["is_installed"] = bool(match)
                if match:
                    updated_data["folder_name"] = match.get("folder_name")
                else:
                    updated_data.pop("folder_name", None)
                self.mod_detail_view.load_mod(
                    updated_data,
                    origin_name=self.mod_detail_view.origin_name,
                    origin_index=self.mod_detail_view.origin_index,
                )
            except Exception as e:
                logger.debug(f"Erreur actualisation mod_detail_view: {e}")

        run_async_ui_task(_fetch, on_finished=_on_fetched)

    def _on_login_success(self, provider_name: str):
        self.switch_page(1)
        if hasattr(self.catalog_view, "start_sync_monitoring"):
            self.catalog_view.start_sync_monitoring()

    def retranslate_ui(self):
        """Exécute l'opération retranslate ui."""
        self.setWindowTitle(tr("app.window_title"))
        self.sidebar.retranslate_ui()
        self.refresh_game_status()
        self.update_nav_badge()

        for view in list(self._views.values()):
            if hasattr(view, "retranslate_ui") and callable(view.retranslate_ui):
                try:
                    view.retranslate_ui()
                except Exception as e:
                    logger.debug(f"Erreur retranslate_ui sur {type(view).__name__}: {e}")

        if (
            1 in self._views
            and hasattr(self._views[1], "provider_drawer")
            and hasattr(self._views[1].provider_drawer, "retranslate_ui")
        ):
            try:
                self._views[1].provider_drawer.retranslate_ui()
            except Exception as e:
                logger.debug(f"Erreur retranslate_ui sur provider_drawer: {e}")

    def refresh_game_status(self):
        """Exécute l'opération refresh game status."""
        if not hasattr(self, "_status_workers"):
            self._status_workers = set()
        worker = BackgroundStatusWorker(self.api_client, self.status_signals)
        self._status_workers.add(worker)
        QThreadPool.globalInstance().start(worker)

    def _on_health_checked(self, success: bool, mods_detected: bool):
        self.sidebar.update_game_status(success, mods_detected)

    def update_nav_badge(self):
        """Exécute l'opération update nav badge."""
        self.refresh_game_status()

    def _on_updates_checked(self, count: int):
        if hasattr(self, "_status_workers") and len(self._status_workers) > 4:
            self._status_workers.clear()
        self.sidebar.update_badge_count(count)

    def _launch_game(self):
        from src.ui.workers.generic_runnable import run_async_ui_task

        def _call_launch():
            return self.api_client.launch_game()

        def _on_launched(res):
            QMessageBox.information(
                self, tr("nav.launch_game_title"), res.get("message", tr("nav.launch_game_success"))
            )

        def _on_error(err):
            QMessageBox.warning(self, tr("dialogs.error_title"), tr("nav.launch_game_error", error=str(err)))

        run_async_ui_task(_call_launch, on_finished=_on_launched, on_error=_on_error, disable_widgets=[self.play_btn])

    def auto_start_background_sync(self):
        """Exécute la vérification et le démarrage de synchro auto en tâche de fond pour ne jamais figer la GUI."""
        from src.ui.workers.generic_runnable import run_async_ui_task

        def _check_and_start_sync():
            try:
                status = self.api_client.get_catalog_sync_status()
                if status.get("is_running", False):
                    return True, False

                self.api_client.start_catalog_sync(max_pages=0, is_background=True)
                return True, True
            except Exception as e:
                logger.debug(f"Vérification automatique de synchronisation au démarrage: {e}")
                return False, False

        def _on_sync_checked(result):
            is_running_or_started, newly_started = result
            if is_running_or_started and hasattr(self.catalog_view, "start_sync_monitoring"):
                self.catalog_view.start_sync_monitoring()
            if newly_started:
                logger.info(
                    "Synchronisation automatique intégrale en tâche de fond démarrée au lancement (connexion OK)."
                )

        run_async_ui_task(_check_and_start_sync, on_finished=_on_sync_checked)

    def closeEvent(self, event):
        """Exécute l'opération closeevent.

        Args:
            event: Paramètre event.
        """
        logger.info("Fermeture de l'application demandée par l'utilisateur...")
        ShutdownManager.trigger_shutdown()
        if 1 in self._views and hasattr(self._views[1], "monitor_timer"):
            try:
                self._views[1].monitor_timer.stop()
            except Exception:
                pass
        for view in list(self._views.values()):
            if hasattr(view, "cleanup") and callable(view.cleanup):
                try:
                    view.cleanup()
                except Exception:
                    pass
        cleanup_all_threads(500)
        super().closeEvent(event)
