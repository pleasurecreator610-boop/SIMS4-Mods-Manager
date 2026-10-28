"""
Unified AuthorInterpellateWidget managing the creator interpellation button,
asynchronous status checking, dynamic styling, and opening ReportPreviewDialog.
Shared between ModDetailView and DependenciesDialog.
"""

from typing import Optional, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QMessageBox

from src.api.client import get_api_client
from src.ui.components.report_preview_dialog import ReportPreviewDialog
from src.i18n import tr
from src.utils.logger import logger
from src.utils.thread_utils import safe_stop_thread, BaseWorker


class CheckReportStatusWorker(BaseWorker):
    """Classe CheckReportStatusWorker : assure la gestion et l'orchestration de Checkreportstatusworker."""

    status_ready = Signal(dict)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self):
        """Exécute l'opération run."""
        self._is_running = True
        try:
            if self._is_cancelled:
                return
            client = get_api_client()
            res = client.check_missing_report(self.payload)
            if not self._is_cancelled:
                self.status_ready.emit(res)
        except Exception as e:
            logger.debug(f"CheckReportStatusWorker error: {e}")
            if not self._is_cancelled:
                self.status_ready.emit(
                    {
                        "can_report": True,
                        "already_reported": False,
                        "formatted_message": "",
                        "author": self.payload.get("author", ""),
                        "is_authenticated": True,
                    }
                )
        finally:
            self._is_running = False


class AuthorInterpellateWidget(QWidget):
    """
    Reusable button component for creator interpellation with live status checking
    and bidirectional override synchronization.
    """

    override_changed = Signal(str, str)
    report_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._check_worker: Optional[CheckReportStatusWorker] = None
        self._status_result: Optional[dict] = None
        self._mod_data: dict = {}
        self._missing_modules: List[str] = []
        self._unnecessary_modules: List[str] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_report = QPushButton(tr("dependencies.btn_report_author"))
        self.btn_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_report.setFixedHeight(34)
        self.btn_report.clicked.connect(self._on_clicked)
        self._apply_checking_style()
        layout.addWidget(self.btn_report)

    def check_status(
        self,
        mod_data: dict,
        missing_modules: List[str],
        unnecessary_modules: List[str],
    ):
        """Starts asynchronous check of report status for this mod."""
        self._mod_data = mod_data
        self._missing_modules = list(missing_modules or [])
        self._unnecessary_modules = list(unnecessary_modules or [])

        if self._check_worker:
            safe_stop_thread(self._check_worker)
            self._check_worker = None

        cat_id = mod_data.get("id") or mod_data.get("catalog_mod_id")
        remote_id = str(mod_data.get("remote_id", ""))
        page_url = mod_data.get("page_url", "")
        source = mod_data.get("source", "loverslab")
        mod_title = mod_data.get("title", "")
        author = mod_data.get("author", "")

        has_remote = bool(cat_id or page_url or remote_id)
        if not has_remote:
            self._apply_can_report_style()
            self.btn_report.setEnabled(True)
            return

        self.btn_report.setEnabled(False)
        self.btn_report.setText(tr("dependencies.checking_report_status"))
        self._apply_checking_style()

        payload = {
            "catalog_mod_id": cat_id,
            "source": source,
            "remote_id": remote_id,
            "page_url": page_url,
            "title": mod_title,
            "author": author,
            "missing_modules": self._missing_modules,
            "unnecessary_modules": self._unnecessary_modules,
        }
        # Worker has no QWidget parent to prevent C++ premature destruction
        self._check_worker = CheckReportStatusWorker(payload)
        self._check_worker.status_ready.connect(self._on_status_ready)
        self._check_worker.start()

    def _on_status_ready(self, res: dict):
        self._status_result = res
        already_reported = res.get("already_reported", False)
        reported_at = res.get("reported_at")

        if already_reported:
            date_display = reported_at or tr("dependencies.previously")
            self.btn_report.setText(tr("dependencies.btn_already_reported", date=date_display))
            self._apply_already_reported_style()
            self.btn_report.setEnabled(False)
            self.btn_report.setToolTip(tr("dependencies.already_reported_tooltip"))
        else:
            self.btn_report.setText(tr("dependencies.btn_report_author"))
            self._apply_can_report_style()
            self.btn_report.setEnabled(True)
            self.btn_report.setToolTip(tr("dependencies.report_author_tooltip"))

    def _on_clicked(self):
        if not self._status_result:
            return

        is_auth = self._status_result.get("is_authenticated", True)
        source = self._mod_data.get("source", "loverslab")
        if not is_auth:
            QMessageBox.warning(
                self,
                tr("dialogs.warning"),
                tr("dependencies.not_authenticated_warning", source=source.capitalize()),
            )
            return

        mod_title = self._mod_data.get("title", "")
        author = self._status_result.get("author") or self._mod_data.get("author", "")
        formatted_msg = self._status_result.get("formatted_message", "")
        cat_id = self._mod_data.get("id") or self._mod_data.get("catalog_mod_id")
        overrides = dict(self._mod_data.get("requirements_overrides", {}) or {})

        dlg = ReportPreviewDialog(
            mod_title=mod_title,
            author=author,
            missing_modules=self._missing_modules,
            unnecessary_modules=self._unnecessary_modules,
            requirements_overrides=overrides,
            source=source,
            page_url=self._mod_data.get("page_url", ""),
            remote_id=str(self._mod_data.get("remote_id", "")),
            catalog_mod_id=cat_id,
            initial_message=formatted_msg,
            initial_subject=self._status_result.get("formatted_subject", ""),
            creator_id=self._status_result.get("creator_id"),
            creator_name=self._status_result.get("creator_name"),
            creator_profile_url=self._status_result.get("creator_profile_url"),
            compose_pm_url=self._status_result.get("compose_pm_url"),
            already_reported=self._status_result.get("already_reported", False),
            reported_at=self._status_result.get("reported_at"),
            parent=self.window(),
        )
        dlg.override_changed.connect(self.override_changed.emit)
        dlg.report_sent.connect(self._on_report_sent_success)
        dlg.exec()

    def _on_report_sent_success(self, reported_at: str):
        self.btn_report.setText(tr("dependencies.btn_already_reported_now"))
        self._apply_already_reported_style()
        self.btn_report.setEnabled(False)
        self.btn_report.setToolTip(tr("dependencies.already_reported_tooltip"))
        self.report_sent.emit(reported_at)

    def _apply_checking_style(self):
        self.btn_report.setStyleSheet("""
            QPushButton {
                background-color: #1e2238;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
        """)

    def _apply_can_report_style(self):
        self.btn_report.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #6366f1);
                color: #ffffff;
                border: 1px solid #818cf8;
                border-radius: 8px;
                padding: 6px 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3730a3, stop:1 #4f46e5);
                border-color: #a5b4fc;
            }
        """)

    def _apply_already_reported_style(self):
        self.btn_report.setStyleSheet("""
            QPushButton {
                background-color: #064e3b;
                color: #a7f3d0;
                border: 1px solid #059669;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
        """)

    def cleanup(self):
        """Exécute l'opération cleanup."""
        if self._check_worker:
            safe_stop_thread(self._check_worker)
            self._check_worker = None
