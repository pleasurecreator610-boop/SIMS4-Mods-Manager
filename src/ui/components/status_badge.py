from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt


class StatusBadge(QLabel):
    """A colorful rounded badge indicating status, platform, or access tier."""

    def __init__(self, text: str, badge_type: str = "default", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(22)
        self.set_badge_type(badge_type)

    def set_badge_type(self, badge_type: str) -> None:
        """Exécute l'opération set badge type.

        Args:
            badge_type: Paramètre badge_type.

        Returns:
            Résultat de l'opération set_badge_type.
        """
        styles = {
            "loverslab": "background-color: #831843; color: #f472b6; border: 1px solid #9d174d;",
            "nsfwmods": "background-color: #3b0764; color: #c084fc; border: 1px solid #6b21a8;",
            "wickedcc": "background-color: #701a75; color: #f0abfc; border: 1px solid #a21caf;",
            "basemental": "background-color: #4c0519; color: #fda4af; border: 1px solid #be123c;",
            "synthira": "background-color: #581c87; color: #d8b4fe; border: 1px solid #7e22ce;",
            "f95zone": "background-color: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c;",
            "smutbase": "background-color: #4a044e; color: #e879f9; border: 1px solid #86198f;",
            "curseforge": "background-color: #431407; color: #fb923c; border: 1px solid #c2410c;",
            "thesimsresource": "background-color: #042f2e; color: #2dd4bf; border: 1px solid #0f766e;",
            "modthesims": "background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7;",
            "simsfinds": "background-color: #1e1b4b; color: #818cf8; border: 1px solid #4f46e5;",
            "nexusmods": "background-color: #78350f; color: #fbbf24; border: 1px solid #d97706;",
            "mmccworld": "background-color: #14532d; color: #86efac; border: 1px solid #16a34a;",
            "deaderpool": "background-color: #1e3a8a; color: #93c5fd; border: 1px solid #2563eb;",
            "scumbumbo": "background-color: #064e3b; color: #6ee7b7; border: 1px solid #059669;",
            "lumpinou": "background-color: #312e81; color: #a5b4fc; border: 1px solid #4f46e5;",
            "gamebanana": "background-color: #422006; color: #fde047; border: 1px solid #ca8a04;",
            "thesimscatalog": "background-color: #134e4a; color: #5eead4; border: 1px solid #0d9488;",
            "itchio": "background-color: #7c2d12; color: #fdba74; border: 1px solid #ea580c;",
            "sims4studio": "background-color: #172554; color: #60a5fa; border: 1px solid #1d4ed8;",
            "littlemssam": "background-color: #065f46; color: #34d399; border: 1px solid #10b981;",
            "sixamcc": "background-color: #3f3f46; color: #e4e4e7; border: 1px solid #71717a;",
            "patreon": "background-color: #7c2d12; color: #fb923c; border: 1px solid #9a3412;",
            "public": "background-color: #064e3b; color: #34d399; border: 1px solid #047857;",
            "unlocked": "background-color: #1e3a5f; color: #60a5fa; border: 1px solid #2563eb;",
            "locked": "background-color: #450a0a; color: #f87171; border: 1px solid #7f1d1d;",
            "installed": "background-color: #14532d; color: #4ade80; border: 1px solid #16a34a;",
            "update": "background-color: #713f12; color: #facc15; border: 1px solid #a16207;",
            "disabled": "background-color: #334155; color: #94a3b8; border: 1px solid #475569;",
            "default": "background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;",
        }
        style = styles.get(badge_type.lower(), styles["default"])
        self.setStyleSheet(f"""
            QLabel {{
                {style}
                border-radius: 11px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)
