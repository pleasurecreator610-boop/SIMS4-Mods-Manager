"""
Unified DependencyCardWidget used across ModDetailView and DependenciesDialog.
Eliminates duplicated styling and layout code for requirements items.
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from src.ui.theme import Theme


class DependencyCardWidget(QFrame):
    """
    Renders a unified dependency card: prefix + title, status badge, and optional action button.
    """

    def __init__(
        self,
        title: str,
        badge_text: str,
        badge_variant: str = "neutral",
        prefix: str = "•",
        action_btn: Optional[QPushButton] = None,
        dashed: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setMinimumHeight(42)
        border_col = "#334155" if not dashed else "#475569"
        bg_col = "#111827" if badge_variant != "info" else "#0f172a"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_col};
                border: 1px {'dashed' if dashed else 'solid'} {border_col};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Prefix + Title
        display_text = f"{prefix} {title}" if prefix else title
        self.lbl_title = QLabel(display_text)
        self.lbl_title.setStyleSheet("color: #f8fafc; font-size: 12px; font-weight: 600;")
        self.lbl_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.lbl_title, stretch=1)

        # Status badge
        self.lbl_badge = QLabel(badge_text)
        self.lbl_badge.setStyleSheet(Theme.badge_style(variant=badge_variant, font_size=11, padding="3px 10px"))
        self.lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_badge)

        # Optional action button
        if action_btn:
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(action_btn)
