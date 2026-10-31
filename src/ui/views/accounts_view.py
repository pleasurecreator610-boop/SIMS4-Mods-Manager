"""
AccountsView: Manages site sessions, interactive Cloudflare solving, tests and resets via API.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Signal, Qt

from src.api.client import get_api_client
from src.core.config import AppConfig
from src.ui.components.progress_dialog import ProgressDialog
from src.ui.components.account_card import AccountCardWidget, LoginWorker
from src.ui.workers.generic_runnable import run_async_ui_task
from src.i18n import tr
from src.utils.logger import logger


__all__ = ["AccountsView", "LoginWorker"]


class AccountsView(QWidget):
    """View to manage site sessions, interactive Cloudflare solving, tests and resets via API."""

    login_successful = Signal(str)  # provider_name
    adult_content_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = get_api_client()
        self.card_widgets = {}
        self._adult_enabled = AppConfig.load().adult_content_enabled
        self.init_ui()

    def init_ui(self):
        """Exécute l'opération init ui."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 28)
        layout.setSpacing(18)

        self.scroll_area.setWidget(container)
        root_layout.addWidget(self.scroll_area)

        # Title
        self.title_lbl = QLabel(tr("accounts.title"))
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel(tr("accounts.subtitle"))
        self.subtitle_lbl.setWordWrap(True)
        self.subtitle_lbl.setStyleSheet("font-size: 13px; color: #94a3b8;")
        layout.addWidget(self.subtitle_lbl)

        # Providers Cards
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(16)

        # 1. LoversLab Card
        self.loverslab_card = AccountCardWidget(
            provider_name="loverslab",
            title_key="accounts.loverslab_title",
            desc_key="accounts.loverslab_desc",
            parent=self,
        )
        self.loverslab_card.clear_requested.connect(self._on_clear_clicked)
        self.loverslab_card.test_requested.connect(self._on_test_clicked)
        self.loverslab_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.loverslab_card)

        # 2. NSFWMods Card
        self.nsfwmods_card = AccountCardWidget(
            provider_name="nsfwmods",
            title_key="accounts.nsfwmods_title",
            desc_key="accounts.nsfwmods_desc",
            parent=self,
        )
        self.nsfwmods_card.clear_requested.connect(self._on_clear_clicked)
        self.nsfwmods_card.test_requested.connect(self._on_test_clicked)
        self.nsfwmods_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.nsfwmods_card)

        # 3. CurseForge Card
        self.curseforge_card = AccountCardWidget(
            provider_name="curseforge",
            title_key="accounts.curseforge_title",
            desc_key="accounts.curseforge_desc",
            parent=self,
        )
        self.curseforge_card.clear_requested.connect(self._on_clear_clicked)
        self.curseforge_card.test_requested.connect(self._on_test_clicked)
        self.curseforge_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.curseforge_card)

        # 4. The Sims Resource Card
        self.tsr_card = AccountCardWidget(
            provider_name="thesimsresource",
            title_key="accounts.thesimsresource_title",
            desc_key="accounts.thesimsresource_desc",
            parent=self,
        )
        self.tsr_card.clear_requested.connect(self._on_clear_clicked)
        self.tsr_card.test_requested.connect(self._on_test_clicked)
        self.tsr_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.tsr_card)

        # 5. ModTheSims Card
        self.modthesims_card = AccountCardWidget(
            provider_name="modthesims",
            title_key="accounts.modthesims_title",
            desc_key="accounts.modthesims_desc",
            parent=self,
        )
        self.modthesims_card.clear_requested.connect(self._on_clear_clicked)
        self.modthesims_card.test_requested.connect(self._on_test_clicked)
        self.modthesims_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.modthesims_card)

        # 6. SimsFinds Card
        self.simsfinds_card = AccountCardWidget(
            provider_name="simsfinds",
            title_key="accounts.simsfinds_title",
            desc_key="accounts.simsfinds_desc",
            parent=self,
        )
        self.simsfinds_card.clear_requested.connect(self._on_clear_clicked)
        self.simsfinds_card.test_requested.connect(self._on_test_clicked)
        self.simsfinds_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.simsfinds_card)

        # 7. Patreon Card
        self.patreon_card = AccountCardWidget(
            provider_name="patreon",
            title_key="accounts.patreon_title",
            desc_key="accounts.patreon_desc",
            parent=self,
        )
        self.patreon_card.clear_requested.connect(self._on_clear_clicked)
        self.patreon_card.test_requested.connect(self._on_test_clicked)
        self.patreon_card.login_requested.connect(self.open_login_window)
        self.cards_layout.addWidget(self.patreon_card)

        # 8. Nexus Mods Card
        self.nexusmods_card = AccountCardWidget(
            provider_name="nexusmods",
            title_key="accounts.nexusmods_title",
            desc_key="accounts.nexusmods_desc",
            parent=self,
        )
        self.nexusmods_card.clear_requested.connect(self._on_clear_clicked)
        self.nexusmods_card.test_requested.connect(self._on_test_clicked)
        self.nexusmods_card.login_requested.connect(self.open_login_window)

        self.btn_nexus_api_key = QPushButton("🔑 Clé API", self.nexusmods_card)
        self.btn_nexus_api_key.setStyleSheet("""
            QPushButton {
                background-color: #065f46;
                color: #a7f3d0;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #047857; color: #ffffff; }
        """)
        self.btn_nexus_api_key.clicked.connect(self._on_prompt_nexus_api_key)
        self.nexusmods_card.add_action_button(self.btn_nexus_api_key)

        self.cards_layout.addWidget(self.nexusmods_card)

        self.cards_by_provider: dict[str, AccountCardWidget] = {
            "loverslab": self.loverslab_card,
            "nsfwmods": self.nsfwmods_card,
            "curseforge": self.curseforge_card,
            "thesimsresource": self.tsr_card,
            "modthesims": self.modthesims_card,
            "simsfinds": self.simsfinds_card,
            "patreon": self.patreon_card,
            "nexusmods": self.nexusmods_card,
        }

        layout.addLayout(self.cards_layout)

        # Subtle banner when adult (+18) platforms are hidden by default
        self.adult_banner = QFrame(self)
        self.adult_banner.setObjectName("AdultHiddenBanner")
        self.adult_banner.setStyleSheet("""
            QFrame#AdultHiddenBanner {
                background-color: #131726;
                border: 1px dashed #334155;
                border-radius: 10px;
            }
            QFrame#AdultHiddenBanner QLabel {
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        ab_layout = QHBoxLayout(self.adult_banner)
        ab_layout.setContentsMargins(16, 12, 16, 12)
        ab_layout.setSpacing(12)

        self.adult_banner_lbl = QLabel(tr("accounts.adult_hidden_notice"))
        self.adult_banner_lbl.setWordWrap(True)
        self.adult_banner_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        ab_layout.addWidget(self.adult_banner_lbl, stretch=1)

        self.btn_enable_adult = QPushButton(tr("accounts.btn_enable_adult"))
        self.btn_enable_adult.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enable_adult.setStyleSheet("""
            QPushButton {
                background-color: #312e81;
                color: #e0e7ff;
                border: 1px solid #6366f1;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #4338ca; color: #ffffff; }
        """)
        self.btn_enable_adult.clicked.connect(lambda: self._on_toggle_adult_clicked(True))
        ab_layout.addWidget(self.btn_enable_adult)
        layout.addWidget(self.adult_banner)

        layout.addStretch()

        # Backward compatibility dictionary for card_widgets
        for card in [
            self.loverslab_card,
            self.nsfwmods_card,
            self.curseforge_card,
            self.tsr_card,
            self.modthesims_card,
            self.simsfinds_card,
            self.patreon_card,
            self.nexusmods_card,
        ]:
            self.card_widgets[card.provider_name] = {
                "title_lbl": card.title_lbl,
                "title_key": card.title_key,
                "desc_lbl": card.desc_lbl,
                "desc_key": card.desc_key,
                "clear_btn": card.clear_btn,
                "test_btn": card.test_btn,
                "login_btn": card.login_btn,
            }

        self.set_adult_content_enabled(self._adult_enabled)
        self.refresh_statuses()

    def _on_toggle_adult_clicked(self, enabled: bool):
        self.set_adult_content_enabled(enabled)
        run_async_ui_task(lambda: self.api_client.update_settings({"adult_content_enabled": enabled}))
        self.adult_content_toggled.emit(enabled)

    def set_adult_content_enabled(self, enabled: bool):
        """Shows or hides LoversLab and NSFWMods credential cards based on adult content setting."""
        self._adult_enabled = bool(enabled)
        self.loverslab_card.setVisible(self._adult_enabled)
        self.nsfwmods_card.setVisible(self._adult_enabled)
        if hasattr(self, "adult_banner"):
            self.adult_banner.setVisible(not self._adult_enabled)

    def retranslate_ui(self):
        """Retranslates all text in AccountsView dynamically."""
        self.title_lbl.setText(tr("accounts.title"))
        self.subtitle_lbl.setText(tr("accounts.subtitle"))
        if hasattr(self, "adult_banner_lbl"):
            self.adult_banner_lbl.setText(tr("accounts.adult_hidden_notice"))
            self.btn_enable_adult.setText(tr("accounts.btn_enable_adult"))
        for card in self.cards_by_provider.values():
            card.retranslate_ui()
        self.refresh_statuses()

    def refresh_statuses(self):
        """Loads account statuses through API /api/accounts asynchronously."""

        def _fetch_accounts():
            client = get_api_client()
            return client.get_accounts()

        def _on_accounts_fetched(accounts):
            for acc in accounts:
                p_name = acc.get("provider_name", "").lower()
                is_member = acc.get("is_member", False)
                is_ready = acc.get("is_ready", False)
                display = acc.get("user_display_name", "")

                card = self.cards_by_provider.get(p_name)
                if not card and p_name:
                    card = AccountCardWidget(
                        provider_name=p_name,
                        title_key=f"Fournisseur : {p_name.capitalize()}",
                        desc_key=f"Gestion de session et anti-bot pour le plugin {p_name.capitalize()}.",
                        parent=self,
                    )
                    card.clear_requested.connect(self._on_clear_clicked)
                    card.test_requested.connect(self._on_test_clicked)
                    card.login_requested.connect(self.open_login_window)
                    self.cards_by_provider[p_name] = card
                    self.card_widgets[p_name] = {
                        "title_lbl": card.title_lbl,
                        "title_key": card.title_key,
                        "desc_lbl": card.desc_lbl,
                        "desc_key": card.desc_key,
                        "clear_btn": card.clear_btn,
                        "test_btn": card.test_btn,
                        "login_btn": card.login_btn,
                    }
                    self.cards_layout.addWidget(card)

                if card:
                    card.update_badge(is_member, is_ready, display)

        def _on_accounts_error(err):
            logger.error(f"Erreur API lors du rafraîchissement des comptes: {err}")

        run_async_ui_task(_fetch_accounts, on_finished=_on_accounts_fetched, on_error=_on_accounts_error)

    def _on_clear_clicked(self, provider_name: str):
        reply = QMessageBox.question(
            self,
            tr("accounts.clear_confirm_title"),
            tr("accounts.clear_confirm_msg", provider=provider_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            card = self.cards_by_provider.get(provider_name)
            widgets_to_disable = [card.clear_btn, card.test_btn, card.login_btn] if card else None

            def _do_clear():
                client = get_api_client()
                return client.clear_account(provider_name)

            def _on_cleared(res):
                self.refresh_statuses()
                QMessageBox.information(
                    self, tr("accounts.clear_success_title"), res.get("message", tr("accounts.clear_success_msg"))
                )

            def _on_clear_error(err):
                QMessageBox.warning(self, tr("dialogs.error_title"), f"{err}")

            run_async_ui_task(
                _do_clear, on_finished=_on_cleared, on_error=_on_clear_error, disable_widgets=widgets_to_disable
            )

    def _on_test_clicked(self, provider_name: str):
        card = self.cards_by_provider.get(provider_name)
        widgets_to_disable = [card.clear_btn, card.test_btn, card.login_btn] if card else None
        if card and hasattr(card, "test_btn"):
            card.test_btn.setText("⏳ Test...")

        def _do_test():
            client = get_api_client()
            res = client.test_account(provider_name)
            ok = res.get("success", False)
            if ok:
                try:
                    sync_st = client.get_catalog_sync_status()
                    if not sync_st.get("is_running", False):
                        client.start_catalog_sync(max_pages=0)
                        logger.info(
                            f"Synchronisation automatique du catalogue lancée suite au test validé de {provider_name}."
                        )
                except Exception as e:
                    logger.debug(f"Impossible de démarrer la synchro auto après test: {e}")
            return res

        def _on_tested(res):
            if card and hasattr(card, "test_btn"):
                card.test_btn.setText(tr("accounts.test_btn"))
            ok = res.get("success", False)
            msg = res.get("message", "")
            if ok:
                QMessageBox.information(self, tr("accounts.test_success_title"), f"{msg}")
            else:
                QMessageBox.warning(self, tr("accounts.test_failed_title"), f"{msg}")
            self.refresh_statuses()

        def _on_test_error(err):
            if card and hasattr(card, "test_btn"):
                card.test_btn.setText(tr("accounts.test_btn"))
            QMessageBox.warning(self, tr("dialogs.error_title"), f"{err}")
            self.refresh_statuses()

        run_async_ui_task(_do_test, on_finished=_on_tested, on_error=_on_test_error, disable_widgets=widgets_to_disable)

    def open_login_window(self, provider_name: str):
        """Exécute l'opération open login window.

        Args:
            provider_name: Paramètre provider_name.
        """
        from src.ui.components.browser_download_dialog import BrowserDownloadDialog

        if not BrowserDownloadDialog.ensure_browser_ready(parent=self):
            return

        self.progress_dlg = ProgressDialog(tr("accounts.login_dlg_title", provider=provider_name), self)
        self.progress_dlg.set_status(tr("accounts.login_dlg_status", provider=provider_name))
        self.progress_dlg.set_details(tr("accounts.login_dlg_details"))
        self.progress_dlg.set_indeterminate(True)
        self.progress_dlg.show()

        self.worker = LoginWorker(provider_name)
        self.worker.finished.connect(self._on_login_finished)
        self.worker.start()

    def _on_login_finished(self, success: bool, msg: str):
        if hasattr(self, "progress_dlg"):
            self.progress_dlg.close()
        provider = getattr(self, "worker", None)
        p_name = provider.provider_name if provider else "compte"

        self.refresh_statuses()

        if success:

            def _trigger_sync():
                client = get_api_client()
                client.start_catalog_sync(max_pages=0)

            run_async_ui_task(_trigger_sync)
            logger.info(
                f"Synchronisation automatique intégrale du catalogue lancée suite à l'authentification de {p_name}."
            )
            QMessageBox.information(self, tr("accounts.login_success_title"), tr("accounts.login_success_msg", msg=msg))
            self.login_successful.emit(p_name)
        else:
            QMessageBox.warning(self, tr("dialogs.info_title"), msg)

    def _on_prompt_nexus_api_key(self):
        """Ouvre un dialogue pour saisir directement la clé API personnelle Nexus Mods."""
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        key, ok = QInputDialog.getText(
            self,
            "Authentification Nexus Mods",
            "Entrez votre clé API personnelle Nexus Mods :\n"
            "(Trouvée sur : https://www.nexusmods.com/users/myaccount?tab=api)\n\n"
            "Cette méthode officielle est directe et contourne tout contrôle antibot.",
            QLineEdit.EchoMode.Normal,
        )
        if ok and key.strip():
            clean_key = key.strip()

            def _do_submit():
                client = get_api_client()
                return client.set_nexusmods_api_key(clean_key)

            def _on_done(res):
                self.refresh_statuses()
                QMessageBox.information(
                    self,
                    "Nexus Mods - Connecté",
                    res.get("message", "Clé API enregistrée avec succès !"),
                )

            def _on_err(err):
                QMessageBox.warning(self, "Erreur de Clé API", f"{err}")

            run_async_ui_task(_do_submit, on_finished=_on_done, on_error=_on_err)
