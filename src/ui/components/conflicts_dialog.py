"""Dialogue interactif d'analyse et de résolution des conflits DBPF entre mods."""

from __future__ import annotations

from typing import Any, Dict
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QFrame,
    QMessageBox,
)

from src.api.client import ApiClient
from src.i18n import tr
from src.ui.workers.generic_runnable import run_async_ui_task
from src.utils.logger import logger


class ConflictCardWidget(QFrame):
    """Carte représentant un conflit TGI spécifique avec les packages en cause."""

    conflict_resolved = Signal()

    def __init__(self, conflict: Dict[str, Any], api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.conflict = conflict
        self.api_client = api_client
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #1a2234;
                border: 1px solid #2d3748;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header row
        header_layout = QHBoxLayout()
        is_stbl = self.conflict.get("is_translation_override", False)
        tgi = self.conflict.get("tgi", "")
        res_name = self.conflict.get("resource_type_name", "Resource")

        badge = QLabel("🌐 TRADUCTION / STBL" if is_stbl else "⚠️ COLLISION TUNING")
        badge.setStyleSheet(
            "background-color: #1e3a8a; color: #93c5fd; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;"
            if is_stbl
            else "background-color: #7f1d1d; color: #fca5a5; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;"
        )
        header_layout.addWidget(badge)

        title_lbl = QLabel(f"<b>{res_name}</b> <span style='color: #94a3b8;'>({tgi})</span>")
        title_lbl.setStyleSheet("color: #f1f5f9; font-size: 12px;")
        header_layout.addWidget(title_lbl, stretch=1)
        layout.addLayout(header_layout)

        # Packages list
        packages = self.conflict.get("conflicting_packages", [])
        for pkg in packages:
            pkg_row = QHBoxLayout()
            pkg_lbl = QLabel(f"• {pkg}")
            pkg_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; font-family: monospace;")
            pkg_lbl.setWordWrap(True)
            pkg_row.addWidget(pkg_lbl, stretch=1)

            btn_action = QPushButton(tr("conflicts.btn_disable") if not pkg.endswith(".disabled") else tr("conflicts.btn_enable"))
            btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_action.setFixedHeight(26)
            is_disabled = pkg.endswith(".disabled")
            btn_action.setStyleSheet(
                "QPushButton { background-color: #064e3b; color: #6ee7b7; border: 1px solid #059669; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background-color: #059669; color: #ffffff; }"
                if is_disabled
                else "QPushButton { background-color: #3b1219; color: #fca5a5; border: 1px solid #991b1b; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background-color: #991b1b; color: #ffffff; }"
            )

            def _make_action(p=pkg, disabled=is_disabled, btn=btn_action):
                def _handler():
                    action = "enable" if disabled else "disable"
                    btn.setEnabled(False)

                    def _do_resolve():
                        return self.api_client.resolve_conflict(p, action=action)

                    def _on_success(res):
                        logger.info(f"Conflit résolu: {res.get('message')}")
                        self.conflict_resolved.emit()

                    def _on_error(err):
                        btn.setEnabled(True)
                        QMessageBox.warning(self, tr("dialogs.error_title"), f"{err}")

                    run_async_ui_task(_do_resolve, on_finished=_on_success, on_error=_on_error)

                return _handler

            btn_action.clicked.connect(_make_action())
            pkg_row.addWidget(btn_action)
            layout.addLayout(pkg_row)


class ConflictsDialog(QDialog):
    """Boîte de dialogue modale affichant les conflits DBPF et permettant leur résolution interactive."""

    def __init__(self, initial_report: Dict[str, Any], api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.report = initial_report
        self.api_client = api_client
        self.setWindowTitle("Diagnostic et Résolution des Conflits DBPF")
        self.resize(780, 560)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header summary
        self.summary_card = QFrame()
        self.summary_card.setStyleSheet("background-color: #1e293b; border-radius: 8px; padding: 10px;")
        summary_layout = QVBoxLayout(self.summary_card)

        self.summary_title = QLabel()
        self.summary_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        summary_layout.addWidget(self.summary_title)

        self.summary_desc = QLabel()
        self.summary_desc.setStyleSheet("font-size: 12px; color: #94a3b8;")
        summary_layout.addWidget(self.summary_desc)

        main_layout.addWidget(self.summary_card)

        # Scroll Area for conflicts list
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.scroll_area.setWidget(self.content_widget)

        main_layout.addWidget(self.scroll_area, stretch=1)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Re-scanner les Conflits")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #0284c7; color: #ffffff; }
        """)
        self.btn_refresh.clicked.connect(self._refresh_conflicts)
        bottom_layout.addWidget(self.btn_refresh)

        bottom_layout.addStretch()

        btn_close = QPushButton("Fermer")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #f8fafc;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)

        main_layout.addLayout(bottom_layout)

        self._render_report(self.report)

    def _render_report(self, report: Dict[str, Any]):
        self.report = report
        count = report.get("conflict_count", 0)
        scanned = report.get("total_packages_scanned", 0)
        trans_count = report.get("translation_override_count", 0)
        crit_count = count - trans_count

        if count == 0:
            self.summary_title.setText("✅ Aucun conflit DBPF détecté !")
            self.summary_desc.setText(f"{scanned} fichiers .package analysés. Toutes les ressources sont uniques et compatibles.")
        else:
            self.summary_title.setText(f"⚠️ {count} Collision(s) Détectée(s) parmi {scanned} Packages")
            desc = f"{crit_count} collision(s) de tuning critique(s)"
            if trans_count > 0:
                desc += f" et {trans_count} remplacement(s) de traduction STBL"
            self.summary_desc.setText(desc + ". Vous pouvez désactiver un package en conflit ci-dessous :")

        # Clear existing items
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        conflicts = report.get("conflicts", [])
        if not conflicts:
            no_conflicts_lbl = QLabel("Aucune collision restante. Vos mods sont désormais parfaitement compatibles !")
            no_conflicts_lbl.setStyleSheet("color: #4ade80; font-size: 13px; font-weight: 600; padding: 20px;")
            no_conflicts_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(no_conflicts_lbl)
        else:
            for c in conflicts:
                card = ConflictCardWidget(c, self.api_client, parent=self)
                card.conflict_resolved.connect(self._refresh_conflicts)
                self.content_layout.addWidget(card)

        self.content_layout.addStretch()

    def _refresh_conflicts(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ Analyse...")

        def _do_fetch():
            return self.api_client.get_mod_conflicts()

        def _on_fetched(new_report):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("🔄 Re-scanner les Conflits")
            self._render_report(new_report)

        def _on_error(err):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("🔄 Re-scanner les Conflits")
            QMessageBox.warning(self, "Erreur", f"Échec du re-scan des conflits : {err}")

        run_async_ui_task(_do_fetch, on_finished=_on_fetched, on_error=_on_error)
