"""
DetailRequirementsWidget: Collapsible requirements, DLCs, and dependencies section
with integrated author interpellation for ModDetailView.
"""

from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
)

from src.application.dependencies.dependency_normalizer import clean_dependency_title, detect_game_dlc_or_base_game
from src.ui.components.dependency_card import DependencyCardWidget
from src.ui.components.author_interpellate_widget import AuthorInterpellateWidget
from src.ui.theme import Theme
from src.i18n import tr


class DetailRequirementsWidget(QWidget):
    """Classe DetailRequirementsWidget : assure la gestion et l'orchestration de Detailrequirementswidget."""

    toggle_comment_requested = Signal(dict, bool)  # dep, to_comment
    override_changed = Signal(str, str)  # module_name, "COMMENT" | "MOD"
    report_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_collapsed = False
        self._unfound_dep_names: List[str] = []
        self._comment_deps: List[dict] = []
        self._mod_data: Dict[str, Any] = {}
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 8)
        main_layout.setSpacing(6)

        self.req_frame = QFrame()
        self.req_frame.setStyleSheet(Theme.card_frame_style(bg="#101424", border="#232d45", padding="10px 14px"))
        self.rf_layout = QVBoxLayout(self.req_frame)
        self.rf_layout.setContentsMargins(10, 8, 10, 8)
        self.rf_layout.setSpacing(6)

        # Header row with collapse button
        hdr_row = QHBoxLayout()
        self.req_title = QLabel(tr("mod_detail.req_section_title"))
        self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        hdr_row.addWidget(self.req_title, stretch=1)

        self.req_collapse_btn = QPushButton(tr("mod_detail.btn_collapse"))
        self.btn_collapse = self.req_collapse_btn
        self.req_collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.req_collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f1f5f9;
            }
        """)
        self.req_collapse_btn.clicked.connect(self._toggle_collapse)
        hdr_row.addWidget(self.req_collapse_btn)
        self.rf_layout.addLayout(hdr_row)

        # Retractable body container
        self.req_body = QWidget()
        self.deps_container = self.req_body
        self.req_body_layout = QVBoxLayout(self.req_body)
        self.req_body_layout.setContentsMargins(0, 0, 0, 0)
        self.req_body_layout.setSpacing(8)

        self.req_desc = QLabel()
        self.req_desc.setWordWrap(True)
        self.req_desc.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        self.req_body_layout.addWidget(self.req_desc)

        # Scrollable container for dependencies and comments list
        self.deps_scroll = QScrollArea()
        self.deps_scroll.setWidgetResizable(True)
        self.deps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.deps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.deps_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #0b0f19;
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.deps_inner_container = QWidget()
        self.deps_inner_container.setStyleSheet("background: transparent;")
        self.deps_layout = QVBoxLayout(self.deps_inner_container)
        self.deps_layout.setContentsMargins(2, 4, 6, 4)
        self.deps_layout.setSpacing(8)
        self.deps_scroll.setWidget(self.deps_inner_container)
        self.req_body_layout.addWidget(self.deps_scroll)

        # Author Interpellation Button Widget
        self.interpellate_widget = AuthorInterpellateWidget(self)
        self.interpellate_widget.override_changed.connect(self.override_changed.emit)
        self.interpellate_widget.report_sent.connect(self.report_sent.emit)
        self.req_body_layout.addWidget(self.interpellate_widget)

        self.rf_layout.addWidget(self.req_body)
        main_layout.addWidget(self.req_frame)
        self.req_frame.setVisible(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_height()

    def _update_responsive_height(self):
        if not hasattr(self, "deps_scroll") or not hasattr(self, "deps_layout"):
            return

        total_items_h = 16  # Base padding
        for i in range(self.deps_layout.count()):
            item = self.deps_layout.itemAt(i)
            if not item:
                continue
            w = item.widget()
            if w and not w.isHidden():
                hint = w.sizeHint().height()
                total_items_h += max(hint, 38) + self.deps_layout.spacing()

        screen = self.screen() or QGuiApplication.primaryScreen()
        screen_h = screen.availableGeometry().height() if screen else 1080
        win_h = self.window().height() if self.window() else screen_h
        max_h = max(380, int(min(screen_h * 0.45, win_h * 0.45)))

        if total_items_h <= max_h:
            self.deps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.deps_scroll.setFixedHeight(max(total_items_h, 48))
        else:
            self.deps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.deps_scroll.setFixedHeight(max_h)

    @property
    def btn_report_author(self) -> QPushButton:
        """Exécute l'opération btn report author.

        Returns:
            Résultat de l'opération btn_report_author.
        """
        return self.interpellate_widget.btn_report

    def _toggle_collapse(self):
        self._is_collapsed = not self._is_collapsed
        self.req_body.setVisible(not self._is_collapsed)
        self.req_collapse_btn.setText(tr("mod_detail.btn_expand") if self._is_collapsed else tr("mod_detail.btn_collapse"))
        if not self._is_collapsed:
            self._update_responsive_height()

    def set_loading(self):
        """Exécute l'opération set loading."""
        self._is_collapsed = False
        self.req_frame.setVisible(True)
        self.req_collapse_btn.setVisible(True)
        self.req_collapse_btn.setText(tr("mod_detail.btn_collapse"))
        self.req_body.setVisible(True)
        self.deps_scroll.setVisible(False)
        self.deps_scroll.setMinimumHeight(0)
        self.req_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        self.req_title.setText(tr("mod_detail.analyzing_reqs"))
        self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #94a3b8;")
        self.req_desc.setText(tr("mod_detail.analyzing_reqs_desc"))
        self.req_desc.setStyleSheet("font-size: 11px; color: #64748b;")
        while self.deps_layout.count():
            it = self.deps_layout.takeAt(0)
            if it and it.widget():
                w = it.widget()
                if w:
                    w.deleteLater()
        self.interpellate_widget.setVisible(False)

    def render_requirements(self, data: dict) -> Dict[str, Any]:
        """Displays requirements status, dependencies list categorized by type, and forum interpellation."""
        self._mod_data = data
        req_text = data.get("requirements_text")
        raw_deps = data.get("dependencies", [])

        while self.deps_layout.count():
            it = self.deps_layout.takeAt(0)
            if it and it.widget():
                w = it.widget()
                if w:
                    w.deleteLater()

        self.req_body.setVisible(True)
        self.req_collapse_btn.setText(tr("mod_detail.btn_collapse"))

        overrides = dict(data.get("requirements_overrides", {}) or {})

        game_dlcs = []
        already_installed = []
        to_install = []
        unfound = []
        comments = []

        for d in raw_deps:
            t = (d.get("title") or "").strip()
            clean_t = clean_dependency_title(t)
            is_base, is_dlc_detected, dlc_name, _ = detect_game_dlc_or_base_game(clean_t)

            if is_base:
                d["is_game_dlc"] = True
                d["status"] = "GAME_DLC"
                d["is_installed"] = True
                d["dlc_name"] = "Jeu de base"
                if not d.get("title") or d.get("title").lower() in ["sims 4", "the sims 4"]:
                    d["title"] = "The Sims 4 (Jeu de base)"
                game_dlcs.append(d)
                continue

            is_dlc = d.get("is_game_dlc", False) or d.get("status") == "GAME_DLC" or is_dlc_detected
            if is_dlc and dlc_name:
                d["dlc_name"] = dlc_name
            is_inst = d.get("is_installed", False) or d.get("status") == "INSTALLED"
            st = d.get("status", "DETECTED_NOT_INSTALLED")

            if is_dlc:
                game_dlcs.append(d)
            elif is_inst:
                already_installed.append(d)
            elif st == "DETECTED_NOT_INSTALLED":
                to_install.append(d)
            elif d.get("is_comment") or st == "COMMENT_NOISE" or overrides.get(t) == "COMMENT":
                d["is_comment"] = True
                comments.append(d)
            else:
                unfound.append(d)

        if (
            (
                not raw_deps
                and not game_dlcs
                and not already_installed
                and not to_install
                and not unfound
                and not comments
            )
            and req_text
            and req_text.strip()
        ):
            clean_req_text = clean_dependency_title(req_text)
            is_bg, is_dlc_text, _, _ = detect_game_dlc_or_base_game(clean_req_text)
            if not is_bg and not is_dlc_text:
                synth_entry = {
                    "title": req_text.strip(),
                    "status": "NOT_DETECTED_FINISHED",
                    "is_installed": False,
                    "is_game_dlc": False,
                }
                if overrides.get(req_text.strip()) == "COMMENT":
                    synth_entry["is_comment"] = True
                    comments.append(synth_entry)
                else:
                    unfound.append(synth_entry)

        self._comment_deps = comments
        has_deps = bool(game_dlcs or already_installed or to_install or unfound or comments)

        if has_deps:
            self.req_frame.setVisible(True)
            self.req_collapse_btn.setVisible(True)

            if unfound:
                self.req_frame.setStyleSheet("""
                    QFrame {
                        background-color: #1e1308;
                        border: 1px solid #d97706;
                        border-radius: 8px;
                        padding: 10px 14px;
                    }
                """)
                total_cnt = len(raw_deps) or len(unfound)
                self.req_title.setText(tr("mod_detail.missing_reqs_title", count=total_cnt))
                self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #fde68a;")
                self.req_desc.setText(tr("mod_detail.missing_reqs_desc"))
                self.req_desc.setStyleSheet("font-size: 11px; color: #fcd34d; margin-top: 2px;")
            else:
                self.req_frame.setStyleSheet("""
                    QFrame {
                        background-color: #0b1524;
                        border: 1px solid #2563eb;
                        border-radius: 8px;
                        padding: 10px 14px;
                    }
                """)
                self.req_title.setText(tr("mod_detail.identified_reqs_title", count=len(raw_deps)))
                self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #93c5fd;")
                self.req_desc.setText(tr("mod_detail.identified_reqs_desc"))
                self.req_desc.setStyleSheet("font-size: 11px; color: #94a3b8; margin-top: 2px;")

            def _add_section_header(title: str, color: str):
                lbl = QLabel(title)
                lbl.setStyleSheet(
                    f"font-size: 12px; font-weight: 700; color: {color}; margin-top: 4px; margin-bottom: 2px;"
                )
                self.deps_layout.addWidget(lbl)

            if game_dlcs:
                _add_section_header(tr("mod_detail.dlcs_header", count=len(game_dlcs)), "#c084fc")
                for d in game_dlcs:
                    t = d.get("title") or d.get("dlc_name") or "DLC Sims 4"
                    is_detected = d.get("is_installed", False)
                    badge_t = tr("dependencies.dlc_detected") if is_detected else tr("dependencies.dlc_check")
                    card = DependencyCardWidget(
                        t, badge_t, badge_variant="success" if is_detected else "purple", prefix="🎮"
                    )
                    self.deps_layout.addWidget(card)

            if to_install:
                _add_section_header(tr("mod_detail.to_install_header", count=len(to_install)), "#60a5fa")
                for d in to_install:
                    t = d.get("title") or f"Mod #{d.get('remote_id')}"
                    card = DependencyCardWidget(t, "📥 " + tr("dependencies.badge_to_install"), badge_variant="info", prefix="•")
                    self.deps_layout.addWidget(card)

            if already_installed:
                _add_section_header(tr("mod_detail.installed_header", count=len(already_installed)), "#4ade80")
                for d in already_installed:
                    t = d.get("title") or f"Mod #{d.get('remote_id')}"
                    card = DependencyCardWidget(t, "✅ " + tr("dependencies.badge_installed"), badge_variant="success", prefix="✓")
                    self.deps_layout.addWidget(card)

            self._unfound_dep_names = []
            if unfound:
                _add_section_header(tr("mod_detail.unfound_header", count=len(unfound)), "#f87171")
                for d in unfound:
                    t = d.get("title") or f"Mod #{d.get('remote_id')}"
                    self._unfound_dep_names.append(t)
                    btn_comm = QPushButton(tr("mod_detail.mark_as_comment"))
                    btn_comm.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_comm.setStyleSheet(Theme.subtle_toggle_button_style(is_active=False))
                    btn_comm.clicked.connect(lambda _, item=d: self.toggle_comment_requested.emit(item, True))
                    card = DependencyCardWidget(
                        t, "⚠️ " + tr("dependencies.unfound_badge"), badge_variant="danger", prefix="⚠️", action_btn=btn_comm
                    )
                    self.deps_layout.addWidget(card)

            if comments:
                _add_section_header(tr("mod_detail.comments_header", count=len(comments)), "#94a3b8")
                comm_note = QLabel(tr("mod_detail.comments_desc"))
                comm_note.setStyleSheet("font-size: 11px; color: #64748b; margin-bottom: 2px;")
                comm_note.setWordWrap(True)
                self.deps_layout.addWidget(comm_note)
                for d in comments:
                    t = d.get("title") or f"Mod #{d.get('remote_id')}"
                    btn_mod = QPushButton(tr("mod_detail.mark_as_mod"))
                    btn_mod.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_mod.setStyleSheet(Theme.subtle_toggle_button_style(is_active=True))
                    btn_mod.clicked.connect(lambda _, item=d: self.toggle_comment_requested.emit(item, False))
                    card = DependencyCardWidget(
                        t, "💬 " + tr("dependencies.badge_comment"), badge_variant="neutral", prefix="💬", action_btn=btn_mod
                    )
                    self.deps_layout.addWidget(card)

            if unfound or comments:
                self.interpellate_widget.setVisible(True)
                self.interpellate_widget.btn_report.setEnabled(False)
            else:
                self.interpellate_widget.setVisible(False)

            self.deps_scroll.setVisible(True)
            self._update_responsive_height()
            QTimer.singleShot(0, self._update_responsive_height)

        else:
            self.interpellate_widget.setVisible(False)
            self._unfound_dep_names = []
            self.deps_scroll.setVisible(False)
            self.deps_scroll.setMinimumHeight(0)
            if req_text and req_text.strip():
                self.req_frame.setVisible(True)
                self.req_collapse_btn.setVisible(True)
                self.req_collapse_btn.setText(tr("mod_detail.btn_collapse"))
                self.req_body.setVisible(True)
                self.req_frame.setStyleSheet("""
                    QFrame {
                        background-color: #101424;
                        border: 1px solid #232d45;
                        border-radius: 8px;
                        padding: 10px 14px;
                    }
                """)
                self.req_title.setText(tr("mod_detail.notes_header"))
                self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #cbd5e1;")
                self.req_desc.setText(req_text)
            else:
                self.req_frame.setVisible(False)

        return {
            "has_deps": has_deps,
            "unfound": unfound,
            "to_install": to_install,
            "already_installed": already_installed,
            "comments": comments,
        }

    def _trigger_check_report_status(self, data: dict, comment_names: Optional[List[str]] = None):
        if comment_names is None:
            comment_names = [
                (c.get("title") or f"Mod #{c.get('remote_id')}")
                for c in self._comment_deps
                if (c.get("title") or c.get("remote_id"))
            ]
        self.interpellate_widget.check_status(data, self._unfound_dep_names, comment_names)

    def _on_report_status_ready(self, res: dict):
        self.interpellate_widget._on_status_ready(res)

    def _on_report_sent_success(self, reported_at: str):
        self.interpellate_widget._on_report_sent_success(reported_at)
