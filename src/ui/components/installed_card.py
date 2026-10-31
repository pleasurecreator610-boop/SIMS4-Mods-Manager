"""Carte InstalledCard représentant un mod installé dans 'Mes Mods' avec recyclage in-place (update_data)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.i18n import tr
from src.ui.components.base_mod_card import BaseModCard
from src.ui.components.dependencies_summary_widget import DependenciesSummaryWidget
from src.ui.components.status_badge import StatusBadge


class InstalledCard(BaseModCard):
    """Carte de mod installé supportant le recyclage d'instance (Object Pooling) via update_data."""

    delete_requested = Signal(dict)
    open_folder_requested = Signal(str)
    toggle_requested = Signal(dict)
    restore_requested = Signal(dict)

    _ACTIVE_TOGGLE_STYLE = """
        QPushButton {
            background-color: #064e3b;
            color: #6ee7b7;
            border: 1px solid #059669;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
            padding: 4px 6px;
        }
        QPushButton:hover {
            background-color: #047857;
            color: #ffffff;
        }
    """

    _INACTIVE_TOGGLE_STYLE = """
        QPushButton {
            background-color: #1f2937;
            color: #9ca3af;
            border: 1px solid #374151;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
            padding: 4px 6px;
        }
        QPushButton:hover {
            background-color: #374151;
            color: #ffffff;
        }
    """

    def __init__(self, mod_data: dict, parent=None):
        super().__init__(mod_data, parent)
        self.thumb_width = 271
        self.thumb_height = 125

        self.setObjectName("InstalledCard")
        self.setFixedWidth(295)
        self.setFixedHeight(400)
        self.init_ui()

    def init_ui(self) -> None:
        """Initialise la structure permanente de la carte installée."""
        self.setStyleSheet("""
            QFrame#InstalledCard {
                background-color: #131726;
                border: 1px solid #1f273d;
                border-radius: 14px;
            }
            QFrame#InstalledCard:hover {
                background-color: #161c30;
                border: 1px solid #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # 1. Thumbnail Image Container via BaseModCard
        self.thumb_label = self._create_thumbnail_container(height=125)
        layout.addWidget(self.thumb_label)

        # 2. Source Badge & Files Count Pill
        self.badges_layout = QHBoxLayout()
        self.badges_layout.setSpacing(6)
        layout.addLayout(self.badges_layout)

        # 3. Title
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setFixedHeight(34)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(self.title_label)

        # 4. Author & Installation Date
        self.meta_lbl = QLabel()
        self.meta_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        layout.addWidget(self.meta_lbl)

        # 5. Folder Name
        self.folder_lbl = QLabel()
        self.folder_lbl.setStyleSheet("font-size: 10px; color: #475569;")
        layout.addWidget(self.folder_lbl)

        # 6. Dependencies Box Container
        self.deps_layout = QVBoxLayout()
        self.deps_layout.setContentsMargins(0, 0, 0, 0)
        self.deps_layout.setSpacing(0)
        layout.addLayout(self.deps_layout)

        layout.addStretch()

        # 7. Action Buttons Bar
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        self.btn_toggle = QPushButton()
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setFixedHeight(30)
        self.btn_toggle.setToolTip(tr("installed.toggle_tooltip"))
        self.btn_toggle.clicked.connect(lambda: self.toggle_requested.emit(self.mod_data))
        actions_layout.addWidget(self.btn_toggle, stretch=1)

        self.btn_folder = QPushButton(tr("installed.btn_folder"))
        self.btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_folder.setFixedHeight(30)
        self.btn_folder.setStyleSheet("""
            QPushButton {
                background-color: #1e2438;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                font-weight: 600;
                font-size: 11px;
                padding: 4px 6px;
            }
            QPushButton:hover {
                background-color: #28314d;
                color: #ffffff;
            }
        """)
        self.btn_folder.clicked.connect(lambda: self.open_folder_requested.emit(self.mod_data.get("folder_name", "")))
        actions_layout.addWidget(self.btn_folder, stretch=1)

        self.btn_delete = QPushButton(tr("installed.btn_delete"))
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setFixedHeight(30)
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #3b1219;
                color: #fca5a5;
                border: 1px solid #7f1d1d;
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                padding: 4px 6px;
            }
            QPushButton:hover {
                background-color: #991b1b;
                color: #ffffff;
                border-color: #dc2626;
            }
        """)
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.mod_data))
        actions_layout.addWidget(self.btn_delete, stretch=1)

        self.btn_restore = QPushButton("↺")
        self.btn_restore.setToolTip(tr("installed.restore_tooltip"))
        self.btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restore.setFixedSize(30, 30)
        self.btn_restore.setStyleSheet("""
            QPushButton {
                background-color: #0f2942;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.btn_restore.clicked.connect(lambda: self.restore_requested.emit(self.mod_data))
        actions_layout.addWidget(self.btn_restore)

        layout.addLayout(actions_layout)

        self.update_data(self.mod_data)

    @staticmethod
    def _clear_sublayout(sublayout) -> None:
        """Vide récursivement un sous-layout."""
        while sublayout.count():
            item = sublayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def update_data(self, mod_data: dict) -> None:
        """Met à jour les données de la carte installée en place (Object Pooling)."""
        self.mod_data = mod_data

        # 1. Badges
        self._clear_sublayout(self.badges_layout)
        source = self.mod_data.get("source", "manual")
        source_badge = StatusBadge(source, badge_type="source")
        self.badges_layout.addWidget(source_badge)

        files_count = self.mod_data.get("files_count", 0)
        files_pill = QLabel(tr("installed.files_count", count=files_count))
        files_pill.setStyleSheet("""
            background-color: #1e253b;
            color: #94a3b8;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 600;
        """)
        self.badges_layout.addWidget(files_pill)
        self.badges_layout.addStretch()

        # 2. Title
        title_text = self.mod_data.get("title", tr("common.untitled"))
        self.title_label.setText(title_text)

        # 3. Author & Installation Date
        author = self.mod_data.get("author") or tr("common.unknown")
        inst_date = self.mod_data.get("installed_date") or ""
        date_str = (
            inst_date[:10]
            if isinstance(inst_date, str)
            else (inst_date.strftime("%d/%m/%Y") if hasattr(inst_date, "strftime") else "")
        )
        self.meta_lbl.setText(f"👤 {author}  •  📅 {date_str or tr('common.recently')}")

        # 4. Folder Name
        folder_name = self.mod_data.get("folder_name", "")
        self.folder_lbl.setText(f"📁 {folder_name}")
        self.folder_lbl.setToolTip(tr("installed.subfolder_tooltip", folder=folder_name))

        # 5. Dependencies
        self._clear_sublayout(self.deps_layout)
        dependencies = self.mod_data.get("dependencies", [])
        if dependencies:
            deps_widget = DependenciesSummaryWidget(dependencies, max_show=2)
            self.deps_layout.addWidget(deps_widget)

        # 6. Action Buttons
        is_enabled = self.mod_data.get("is_enabled", True)
        self.btn_toggle.setText(tr("installed.status_active") if is_enabled else tr("installed.status_inactive"))
        self.btn_toggle.setStyleSheet(self._ACTIVE_TOGGLE_STYLE if is_enabled else self._INACTIVE_TOGGLE_STYLE)

        backup_path = self.mod_data.get("backup_path")
        self.btn_restore.setVisible(bool(backup_path))

        # 7. Thumbnail
        self._load_thumbnail_async()

    def mousePressEvent(self, event) -> None:
        """Émet details_requested si le clic a lieu hors des boutons d'action."""
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if child is not None and (
                (hasattr(self, "btn_folder") and (child == self.btn_folder or self.btn_folder.isAncestorOf(child)))
                or (hasattr(self, "btn_delete") and (child == self.btn_delete or self.btn_delete.isAncestorOf(child)))
                or (hasattr(self, "btn_toggle") and (child == self.btn_toggle or self.btn_toggle.isAncestorOf(child)))
                or (
                    hasattr(self, "btn_restore") and (child == self.btn_restore or self.btn_restore.isAncestorOf(child))
                )
            ):
                super().mousePressEvent(event)
                return
            self.details_requested.emit(self.mod_data)
        super().mousePressEvent(event)
