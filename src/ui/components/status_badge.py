from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt

from src.core.provider_metadata import PROVIDER_SPECS


_BASE_STATUS_STYLES = {
    **{k: spec.badge_style for k, spec in PROVIDER_SPECS.items()},
    "public": "background-color: #064e3b; color: #34d399; border: 1px solid #047857;",
    "unlocked": "background-color: #1e3a5f; color: #60a5fa; border: 1px solid #2563eb;",
    "locked": "background-color: #450a0a; color: #f87171; border: 1px solid #7f1d1d;",
    "installed": "background-color: #14532d; color: #4ade80; border: 1px solid #16a34a;",
    "update": "background-color: #713f12; color: #facc15; border: 1px solid #a16207;",
    "disabled": "background-color: #334155; color: #94a3b8; border: 1px solid #475569;",
    "default": "background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;",
}


class StatusBadge(QLabel):
    """A colorful rounded badge indicating status, platform, or access tier."""

    def __init__(self, text: str, badge_type: str = "default", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(22)
        self.set_badge_type(badge_type)

    def set_badge_type(self, badge_type: str) -> None:
        """Exécute l'opération set badge type."""
        style = _BASE_STATUS_STYLES.get(badge_type.lower(), _BASE_STATUS_STYLES["default"])
        self.setStyleSheet(f"""
            QLabel {{
                {style}
                border-radius: 11px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)
