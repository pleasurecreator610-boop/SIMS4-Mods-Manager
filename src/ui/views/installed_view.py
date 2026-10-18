from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from src.api.client import get_api_client
from src.ui.components.installed_card import InstalledCard
from src.ui.components.responsive_card_grid import ResponsiveCardGrid
from src.ui.utils.dialog_helper import DialogHelper
from src.ui.workers.installed_workers import ConflictsWorker, InstalledFetchWorker, InstalledScanWorker
from src.ui.workers.generic_runnable import run_async_ui_task
from src.utils.thread_utils import safe_stop_thread
from src.i18n import tr
from src.utils.logger import logger



class InstalledView(QWidget):
    """
    Modern grid view managing installed Sims 4 mods.
    Displays rich cards with cover previews, metadata, direct folder access, and deletion.
    """

    details_requested = Signal(dict)
    mods_changed = Signal()

    def __init__(self, parent=None, api_client=None):
        super().__init__(parent)
        self.api_client = api_client or get_api_client()
        self.all_mods = []
        self._fetch_worker = None
        self._scan_worker = None
        self._conflicts_worker = None
        self.init_ui()

    def init_ui(self):
        """Exécute l'opération init ui."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        self.counter_label = QLabel(tr("installed.title"))
        self.counter_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.counter_label)

        self.badge_count = QLabel(tr("installed.badge_count", count=0))
        self.badge_count.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.badge_count)

        header_layout.addStretch()

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("installed.search_placeholder"))
        self.search_input.setFixedWidth(240)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #131726;
                color: #f8fafc;
                border: 1px solid #232d45;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
        """)
        self.search_input.textChanged.connect(self._filter_cards)
        header_layout.addWidget(self.search_input)

        # Conflicts Diagnostic Button
        self.conflicts_btn = QPushButton(tr("installed.conflicts_btn"))
        self.conflicts_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.conflicts_btn.setToolTip(tr("installed.conflicts_btn_tooltip"))
        self.conflicts_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e1a47;
                color: #e9d5ff;
                border: 1px solid #6b21a8;
                border-radius: 8px;
                padding: 7px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #4c1d95; color: #ffffff; }
        """)
        self.conflicts_btn.clicked.connect(self.check_conflicts)
        header_layout.addWidget(self.conflicts_btn)

        # Scan Button
        self.scan_btn = QPushButton(tr("installed.scan_btn"))
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #28314d; color: #ffffff; }
        """)
        self.scan_btn.clicked.connect(self.scan_mods_folder)
        header_layout.addWidget(self.scan_btn)

        # Open Mods Folder Button
        self.open_folder_btn = QPushButton(tr("installed.open_folder_btn"))
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: #ffffff;
                border-radius: 8px;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5); }
        """)
        self.open_folder_btn.clicked.connect(self.open_mods_folder)
        header_layout.addWidget(self.open_folder_btn)

        layout.addLayout(header_layout)

        # 2. Scroll Area for Cards Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        self.card_grid = ResponsiveCardGrid(min_card_width=295, spacing=16)
        scroll.setWidget(self.card_grid)
        layout.addWidget(scroll, stretch=1)

        self.refresh_mods()

    def refresh_mods(self):
        """Fetches installed mods from API asynchronously to prevent UI freezing."""
        safe_stop_thread(self._fetch_worker)
        self._fetch_worker = InstalledFetchWorker(self.api_client)
        self._fetch_worker.data_ready.connect(self._on_mods_loaded)
        self._fetch_worker.error_signal.connect(lambda err: logger.error(f"Erreur chargement mods: {err}"))
        self._fetch_worker.start()

    def _on_mods_loaded(self, mods: list):
        self.all_mods = mods
        total = len(self.all_mods)
        self.badge_count.setText(tr("installed.badge_count", count=total))
        self._populate_grid(self.all_mods)

    def refresh_table(self):
        """Compatibility alias for refresh_mods."""
        self.refresh_mods()

    def _filter_cards(self):
        query = self.search_input.text().strip().lower()
        if not query:
            self._populate_grid(self.all_mods)
            return

        filtered = [
            m
            for m in self.all_mods
            if query in m.get("title", "").lower()
            or query in m.get("folder_name", "").lower()
            or query in m.get("author", "").lower()
            or query in m.get("source", "").lower()
        ]
        self._populate_grid(filtered)

    def _populate_grid(self, mods_list: list):
        if not mods_list:
            self.card_grid.set_empty_message(tr("installed.empty_desc"))
            return

        new_cards = []
        for m in mods_list:
            card = InstalledCard(m, parent=self)
            card.delete_requested.connect(self._on_delete_mod)
            card.toggle_requested.connect(self._on_toggle_mod)
            card.restore_requested.connect(self._on_restore_mod)
            card.open_folder_requested.connect(self.open_mod_folder)
            card.details_requested.connect(self.details_requested.emit)
            new_cards.append(card)

        self.card_grid.set_cards(new_cards)

    def _on_toggle_mod(self, mod_data: dict):
        """Active ou désactive un mod via l'API en arrière-plan sans bloquer la GUI."""
        mod_id = mod_data.get("id")
        if not mod_id:
            return
        title = mod_data.get("title", "Mod")
        is_enabled = mod_data.get("is_enabled", True)
        target_state = not is_enabled

        def _do_execute_toggle():
            def _do_toggle():
                return self.api_client.toggle_mod(mod_id, enabled=target_state)

            def _on_toggle_finished(res):
                if res.get("success", False):
                    action_str = "activé" if target_state else "désactivé"
                    logger.info(f"Mod '{title}' {action_str} avec succès.")
                    self.refresh_mods()
                    self.mods_changed.emit()
                else:
                    DialogHelper.error(self, tr("dialogs.error_title"), res.get("message", "Échec du changement d'état."))

            def _on_toggle_error(err):
                logger.error(f"Erreur lors du basculement d'état du mod {mod_id}: {err}")
                DialogHelper.error(self, tr("dialogs.error_title"), f"{err}")

            run_async_ui_task(_do_toggle, on_finished=_on_toggle_finished, on_error=_on_toggle_error)

        if not target_state:
            def _fetch_deps():
                try:
                    dep_res = self.api_client.get_mod_dependents(mod_id)
                    return dep_res.get("dependents", [])
                except Exception as e:
                    logger.debug(f"Could not check dependents for mod {mod_id}: {e}")
                    return []

            def _on_deps_fetched(dependents):
                if dependents:
                    dep_lines = "\n".join(f"  • {d.get('title', 'Mod')} ({d.get('folder_name', '')})" for d in dependents)
                    confirmed = DialogHelper.confirm(
                        self,
                        title=tr("installed.dep_warning_title"),
                        message=f"Attention : Désactiver '{title}' risque d'affecter le fonctionnement des {len(dependents)} mod(s) qui en dépendent :\n\n{dep_lines}\n\nSouhaitez-vous quand même désactiver ce mod ?",
                        confirm_text=tr("installed.btn_disable_anyway", default="Désactiver quand même"),
                        cancel_text=tr("installed.btn_cancel"),
                        is_destructive=True,
                    )
                    if not confirmed:
                        return
                _do_execute_toggle()

            run_async_ui_task(_fetch_deps, on_finished=_on_deps_fetched)
        else:
            _do_execute_toggle()

    def _on_restore_mod(self, mod_data: dict):
        """Confirme et restaure la version précédente d'un mod via sa sauvegarde."""
        mod_id = mod_data.get("id")
        title = mod_data.get("title", "Mod")
        if not mod_id:
            return

        confirmed = DialogHelper.confirm(
            self,
            title="Restaurer la Sauvegarde",
            message=f"Voulez-vous restaurer la version précédente sauvegardée pour '{title}' ?\n\nLes fichiers actuels seront remplacés par l'archive de sauvegarde.",
            confirm_text="Restaurer",
            cancel_text=tr("installed.btn_cancel"),
            is_destructive=False,
        )
        if not confirmed:
            return

        def _do_restore():
            return self.api_client.restore_mod_backup(mod_id)

        def _on_restored(res):
            if res.get("success", False):
                QMessageBox.information(
                    self,
                    "Restauration Réussie",
                    res.get("message", f"La version précédente de '{title}' a été restaurée."),
                )
                self.refresh_mods()
                self.mods_changed.emit()
            else:
                DialogHelper.error(self, tr("dialogs.error_title"), res.get("message", "Échec de la restauration."))

        def _on_error(err):
            logger.error(f"Erreur restauration mod {mod_id}: {err}")
            DialogHelper.error(self, tr("dialogs.error_title"), f"{err}")

        run_async_ui_task(_do_restore, on_finished=_on_restored, on_error=_on_error)

    def check_conflicts(self):
        """Lance l'analyse DBPF des conflits de ressources de manière asynchrone."""
        self.conflicts_btn.setEnabled(False)
        self.conflicts_btn.setText(tr("installed.conflicts_btn_analyzing"))

        safe_stop_thread(self._conflicts_worker)
        self._conflicts_worker = ConflictsWorker(self.api_client)

        def _on_conflicts_ready(report: dict):
            self.conflicts_btn.setEnabled(True)
            self.conflicts_btn.setText(tr("installed.conflicts_btn"))
            from src.ui.components.conflicts_dialog import ConflictsDialog

            dialog = ConflictsDialog(report, self.api_client, parent=self)
            dialog.exec()
            self.refresh_mods()
            self.mods_changed.emit()

        def _on_conflicts_error(err: str):
            self.conflicts_btn.setEnabled(True)
            self.conflicts_btn.setText(tr("installed.conflicts_btn"))
            QMessageBox.critical(self, "Erreur Diagnostic Conflits", f"L'analyse a échoué : {err}")

        self._conflicts_worker.finished_signal.connect(_on_conflicts_ready)
        self._conflicts_worker.error_signal.connect(_on_conflicts_error)
        self._conflicts_worker.start()

    def _on_delete_mod(self, mod_data: dict):
        """Confirme et désinstalle le mod via l'API sans bloquer la GUI."""
        title = mod_data.get("title", tr("common.untitled"))
        mod_id = mod_data.get("id")
        folder_name = mod_data.get("folder_name", "")
        if not mod_id:
            return

        def _fetch_deps():
            try:
                dep_res = self.api_client.get_mod_dependents(mod_id)
                return dep_res.get("dependents", [])
            except Exception as e:
                logger.debug(f"Could not check dependents for mod {mod_id}: {e}")
                return []

        def _on_deps_fetched(dependents):
            if dependents:
                dep_lines = "\n".join(f"  • {d.get('title', 'Mod')} ({d.get('folder_name', '')})" for d in dependents)
                confirmed = DialogHelper.confirm(
                    self,
                    title=tr("installed.dep_warning_title"),
                    message=tr("installed.dep_warning_msg", title=title, count=len(dependents), deps=dep_lines),
                    confirm_text=tr("installed.btn_delete_anyway"),
                    cancel_text=tr("installed.btn_cancel"),
                    is_destructive=True,
                )
                if not confirmed:
                    return
            else:
                confirmed = DialogHelper.confirm(
                    self,
                    title=tr("installed.delete_confirm_title"),
                    message=tr("installed.delete_confirm_msg", title=title, folder=folder_name),
                    is_destructive=True,
                )
                if not confirmed:
                    return

            def _do_uninstall():
                return self.api_client.uninstall_mod(mod_id)

            def _on_uninstall_finished(res):
                if res.get("success", False):
                    logger.info(f"Mod '{title}' désinstallé avec succès.")
                    DialogHelper.success(
                        self, tr("installed.delete_success_title"), tr("installed.delete_success_msg", title=title)
                    )
                    self.mods_changed.emit()
                else:
                    logger.error(f"Échec de la suppression de '{title}': {res.get('message')}")
                    DialogHelper.error(self, tr("dialogs.error_title"), res.get("message", tr("dialogs.error_title")))
                self.refresh_mods()

            def _on_uninstall_error(err):
                logger.error(f"Erreur lors de la désinstallation du mod {mod_id}: {err}")
                DialogHelper.error(self, tr("dialogs.error_title"), f"{err}")

            run_async_ui_task(_do_uninstall, on_finished=_on_uninstall_finished, on_error=_on_uninstall_error)

        run_async_ui_task(_fetch_deps, on_finished=_on_deps_fetched)

    def scan_mods_folder(self):
        """Exécute le scan des mods de façon asynchrone pour ne jamais figer l'interface."""
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("⏳ Scan en cours...")

        safe_stop_thread(self._scan_worker)
        self._scan_worker = InstalledScanWorker(self.api_client)

        def _on_scan_finished(res: dict):
            self.scan_btn.setEnabled(True)
            self.scan_btn.setText(tr("installed.scan_btn"))
            msg = res.get("message", "Scan terminé.")
            logger.info(f"Scan des mods effectué : {msg}")
            QMessageBox.information(self, tr("installed.scan_finished_title"), msg)
            self.refresh_mods()
            self.mods_changed.emit()

        def _on_scan_error(err: str):
            self.scan_btn.setEnabled(True)
            self.scan_btn.setText(tr("installed.scan_btn"))
            logger.error(f"Erreur scan dossier Mods: {err}")
            QMessageBox.critical(self, tr("installed.scan_error_title"), f"{err}")

        self._scan_worker.finished_signal.connect(_on_scan_finished)
        self._scan_worker.error_signal.connect(_on_scan_error)
        self._scan_worker.start()

    def open_mods_folder(self):
        """Exécute l'ouverture du dossier mods de façon asynchrone."""
        def _on_err(err: str) -> None:
            QMessageBox.warning(self, tr("dialogs.error_title"), f"{err}")

        run_async_ui_task(
            self.api_client.open_folder,
            on_error=_on_err,
        )

    def open_mod_folder(self, folder_name: str):
        """Exécute l'ouverture du sous-dossier mod de façon asynchrone."""
        def _on_err(err: str) -> None:
            QMessageBox.warning(self, tr("dialogs.error_title"), f"{err}")

        run_async_ui_task(
            lambda: self.api_client.open_folder(folder_name=folder_name),
            on_error=_on_err,
        )


    def retranslate_ui(self):
        """Retranslates all text elements in InstalledView."""
        self.counter_label.setText(tr("installed.title"))
        self.search_input.setPlaceholderText(tr("installed.search_placeholder"))
        self.conflicts_btn.setText(tr("installed.conflicts_btn"))
        self.conflicts_btn.setToolTip(tr("installed.conflicts_btn_tooltip"))
        self.scan_btn.setText(tr("installed.scan_btn"))
        self.open_folder_btn.setText(tr("installed.open_folder_btn"))
        count = len(self.all_mods)
        self.badge_count.setText(tr("installed.badge_count", count=count))
        self._filter_cards()
