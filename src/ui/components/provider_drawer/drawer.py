"""
ProviderDrawer: Modular retractable right-side satellite drawer for multi-provider status,
subcategory progress monitoring across all platforms (CurseForge, The Sims Resource, LoversLab, NSFWMods),
and individual site scraping controls.
"""

from typing import Dict, Any, Tuple, Optional
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal

from src.core.config import AppConfig
from src.i18n import tr
from src.ui.components.provider_drawer.drawer_styles import DrawerStyles
from src.ui.components.provider_drawer.subcategory_row import SubcategoryRowWidget
from src.ui.components.provider_drawer.provider_cards import (
    ProviderScraperDrawerCard,
    LoversLabDrawerCard,
    PatreonDrawerCard,
    NSFWMODS_SUBCATS,
    CURSEFORGE_SUBCATS,
    TSR_SUBCATS,
    MODTHESIMS_SUBCATS,
    SIMSFINDS_SUBCATS,
    NEXUSMODS_SUBCATS,
    MMCCWORLD_SUBCATS,
)


class ProviderDrawer(QWidget):
    """
    Modular retractable right-side satellite drawer for provider status,
    subcategory progress monitoring across all platforms, and scraping controls.
    """

    start_requested = Signal(str)  # provider name
    pause_requested = Signal(str)  # provider name
    resume_requested = Signal(str)  # provider name
    stop_requested = Signal(str)  # provider name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_status: Optional[Dict[str, Any]] = None
        self._last_tab_states: Dict[QLabel, str] = {}
        self._adult_enabled: bool = AppConfig.load().adult_content_enabled
        self._init_ui()
        self.set_adult_content_enabled(self._adult_enabled)

    def _create_edge_pill(self, text: str, tooltip: str) -> QLabel:
        pill = QLabel(text)
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setCursor(Qt.CursorShape.PointingHandCursor)
        pill.setToolTip(tooltip)
        pill.mousePressEvent = lambda e: self.toggle_drawer()  # type: ignore[method-assign]
        self._style_site_tab_pill(pill, "OK", text)
        return pill

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Persistent Edge Tab (Always visible on right edge)
        self.tab_widget = QFrame()
        self.tab_widget.setObjectName("DrawerEdgeTab")
        self.tab_widget.setFixedWidth(138)
        self.tab_widget.setStyleSheet("""
            QFrame#DrawerEdgeTab {
                background-color: #0c1020;
                border: 1px solid #1e2844;
                border-radius: 10px;
            }
        """)
        tab_layout = QVBoxLayout(self.tab_widget)
        tab_layout.setContentsMargins(5, 6, 5, 6)
        tab_layout.setSpacing(4)

        self.btn_toggle_drawer = QPushButton(tr("drawer.btn_toggle_collapsed"))
        self.btn_toggle_drawer.setFixedHeight(30)
        self.btn_toggle_drawer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_drawer.setToolTip(tr("drawer.btn_toggle_tip"))
        self.btn_toggle_drawer.clicked.connect(self.toggle_drawer)
        self._style_toggle_button("OK")
        tab_layout.addWidget(self.btn_toggle_drawer)

        # Scrollable edge pills container to support all screens smoothly
        edge_scroll = QScrollArea()
        edge_scroll.setWidgetResizable(True)
        edge_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        edge_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        edge_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 4px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #222d52;
                border-radius: 2px;
            }
        """)
        edge_container = QWidget()
        edge_container.setStyleSheet("background: transparent;")
        edge_container_layout = QVBoxLayout(edge_container)
        edge_container_layout.setContentsMargins(0, 2, 0, 2)
        edge_container_layout.setSpacing(4)

        # Site status badges on collapsed edge for all platforms
        self.tab_curseforge_pill = self._create_edge_pill("CurseForge 🟢", "Statut CurseForge - Cliquer pour détails")
        edge_container_layout.addWidget(self.tab_curseforge_pill)

        self.tab_tsr_pill = self._create_edge_pill("TSR 🟢", "Statut The Sims Resource - Cliquer pour détails")
        edge_container_layout.addWidget(self.tab_tsr_pill)

        self.tab_modthesims_pill = self._create_edge_pill("ModTheSims 🟢", "Statut ModTheSims - Cliquer pour détails")
        edge_container_layout.addWidget(self.tab_modthesims_pill)

        self.tab_simsfinds_pill = self._create_edge_pill("SimsFinds 🟢", "Statut SimsFinds - Cliquer pour détails")
        edge_container_layout.addWidget(self.tab_simsfinds_pill)

        self.tab_nexusmods_pill = self._create_edge_pill("Nexus Mods 🟢", "Statut Nexus Mods - Cliquer pour détails")
        edge_container_layout.addWidget(self.tab_nexusmods_pill)

        self.tab_mmccworld_pill = self._create_edge_pill("MMCCWorld 🟢", "Statut Maxis Match CC World - Cliquer pour détails")
        edge_container_layout.addWidget(self.tab_mmccworld_pill)

        self.tab_patreon_pill = self._create_edge_pill("Patreon 🟢", tr("drawer.pill_tip_patreon"))
        edge_container_layout.addWidget(self.tab_patreon_pill)

        self.tab_loverslab_pill = self._create_edge_pill("LoversLab 🟢", tr("drawer.pill_tip_ll"))
        edge_container_layout.addWidget(self.tab_loverslab_pill)

        self.tab_nsfwmods_pill = self._create_edge_pill("NSFWMods 🟢", "Statut NSFWMods - Cliquer pour détails")
        edge_container_layout.addWidget(self.tab_nsfwmods_pill)

        edge_container_layout.addStretch()
        edge_scroll.setWidget(edge_container)
        tab_layout.addWidget(edge_scroll)

        main_layout.addWidget(self.tab_widget)

        # 2. Retractable Drawer Panel
        self.drawer_panel = QFrame()
        self.drawer_panel.setObjectName("DrawerPanel")
        self.drawer_panel.setFixedWidth(365)
        self.drawer_panel.setVisible(False)
        self.drawer_panel.setStyleSheet("""
            QFrame#DrawerPanel {
                background-color: #0e1224;
                border: 1px solid #1e2844;
                border-radius: 12px;
            }
        """)
        d_layout = QVBoxLayout(self.drawer_panel)
        d_layout.setContentsMargins(12, 12, 12, 12)
        d_layout.setSpacing(10)

        # Drawer Header
        d_header = QHBoxLayout()
        self.d_title = QLabel(tr("drawer.title"))
        self.d_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f8fafc; background: transparent; border: none;")
        d_header.addWidget(self.d_title)
        d_header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                font-weight: 700;
                font-size: 14px;
            }
            QPushButton:hover { color: #f8fafc; }
        """)
        btn_close.clicked.connect(self.toggle_drawer)
        d_header.addWidget(btn_close)
        d_layout.addLayout(d_header)

        # Scrollable container for all provider cards
        drawer_scroll = QScrollArea()
        drawer_scroll.setWidgetResizable(True)
        drawer_scroll.setStyleSheet("background-color: transparent; border: none;")

        providers_container = QWidget()
        providers_container.setStyleSheet("background-color: transparent;")
        providers_layout = QVBoxLayout(providers_container)
        providers_layout.setContentsMargins(0, 0, 4, 0)
        providers_layout.setSpacing(10)

        # --- 1. CurseForge Provider Card ---
        self.cf_card = ProviderScraperDrawerCard(
            provider_name="curseforge",
            display_name="CurseForge",
            subcategories_meta=CURSEFORGE_SUBCATS,
            expanded_by_default=True,
            parent=self,
        )

        # --- 2. The Sims Resource Provider Card ---
        self.tsr_card = ProviderScraperDrawerCard(
            provider_name="thesimsresource",
            display_name="The Sims Resource",
            subcategories_meta=TSR_SUBCATS,
            expanded_by_default=False,
            parent=self,
        )

        # --- 3. ModTheSims Provider Card ---
        self.mts_card = ProviderScraperDrawerCard(
            provider_name="modthesims",
            display_name="ModTheSims",
            subcategories_meta=MODTHESIMS_SUBCATS,
            expanded_by_default=False,
            parent=self,
        )

        # --- 4. SimsFinds Provider Card ---
        self.sf_card = ProviderScraperDrawerCard(
            provider_name="simsfinds",
            display_name="SimsFinds",
            subcategories_meta=SIMSFINDS_SUBCATS,
            expanded_by_default=False,
            parent=self,
        )

        # --- 5. Nexus Mods Provider Card ---
        self.nexus_card = ProviderScraperDrawerCard(
            provider_name="nexusmods",
            display_name="Nexus Mods",
            subcategories_meta=NEXUSMODS_SUBCATS,
            expanded_by_default=False,
            parent=self,
        )

        # --- 6. Maxis Match CC World Provider Card ---
        self.mmccw_card = ProviderScraperDrawerCard(
            provider_name="mmccworld",
            display_name="Maxis Match CC World",
            subcategories_meta=MMCCWORLD_SUBCATS,
            expanded_by_default=False,
            parent=self,
        )

        # --- 7. LoversLab Provider Card (+18) ---
        self.ll_card = LoversLabDrawerCard(self)

        # --- 8. NSFWMods Provider Card (+18) ---
        self.nm_card = ProviderScraperDrawerCard(
            provider_name="nsfwmods",
            display_name="NSFWMods",
            subcategories_meta=NSFWMODS_SUBCATS,
            expanded_by_default=False,
            parent=self,
        )

        # --- 9. Patreon Card ---
        self.patreon_card = PatreonDrawerCard(self)

        self.scraper_cards = [
            self.cf_card,
            self.tsr_card,
            self.mts_card,
            self.sf_card,
            self.nexus_card,
            self.mmccw_card,
            self.ll_card,
            self.nm_card,
        ]

        for card in self.scraper_cards:
            card.start_requested.connect(self.start_requested.emit)
            card.pause_requested.connect(self.pause_requested.emit)
            card.resume_requested.connect(self.resume_requested.emit)
            card.stop_requested.connect(self.stop_requested.emit)
            providers_layout.addWidget(card)

        providers_layout.addWidget(self.patreon_card)

        providers_layout.addStretch()
        drawer_scroll.setWidget(providers_container)
        d_layout.addWidget(drawer_scroll)

        main_layout.addWidget(self.drawer_panel)

    def set_adult_content_enabled(self, enabled: bool):
        """Shows or hides LoversLab and NSFWMods pills and cards based on adult content setting."""
        self._adult_enabled = bool(enabled)
        self.tab_loverslab_pill.setVisible(self._adult_enabled)
        self.tab_nsfwmods_pill.setVisible(self._adult_enabled)
        self.ll_card.setVisible(self._adult_enabled)
        self.nm_card.setVisible(self._adult_enabled)

    # Backward compatible attributes delegated to LoversLab card
    @property
    def subcat_widgets(self) -> Dict[str, SubcategoryRowWidget]:
        return self.ll_card.subcat_widgets

    @property
    def subcat_rows(self) -> Dict[str, Tuple[QLabel, QLabel, QLabel]]:
        return self.ll_card.subcat_rows

    @property
    def drawer_status_pill(self) -> QLabel:
        return self.ll_card.drawer_status_pill

    @property
    def drawer_progress_bar(self):
        return self.ll_card.drawer_progress_bar

    @property
    def btn_resync(self) -> QPushButton:
        return self.ll_card.btn_resync

    @property
    def btn_pause_resume(self) -> QPushButton:
        return self.ll_card.btn_pause_resume

    @property
    def btn_stop(self) -> QPushButton:
        return self.ll_card.btn_stop

    def toggle_drawer(self):
        """Toggles visibility of the drawer panel."""
        new_vis = not self.drawer_panel.isVisible()
        self.drawer_panel.setVisible(new_vis)
        arrow = "▶" if new_vis else "◀"
        cur_t = self.btn_toggle_drawer.text()
        parts = cur_t.rsplit(" ", 1)
        base = parts[0] if len(parts) > 1 else cur_t
        self.btn_toggle_drawer.setText(f"{base} {arrow}")

    def _update_single_edge_pill(self, pill: QLabel, short_name: str, card: ProviderScraperDrawerCard):
        state = card.last_computed_state
        pct = card.last_computed_pct
        if state == "ERROR":
            self._style_site_tab_pill(pill, "ERROR", f"{short_name} 🔴")
        elif state == "PAUSED":
            self._style_site_tab_pill(pill, "PAUSED", f"{short_name} ⏸️ {pct}%")
        elif state == "RUNNING":
            self._style_site_tab_pill(pill, "RUNNING", f"{short_name} 🔵 {pct}%")
        else:
            self._style_site_tab_pill(pill, "OK", f"{short_name} 🟢")

    def update_sync_status(self, status: Dict[str, Any]):
        """Updates drawer status, progress bars, action buttons, and persistent edge tab for all providers."""
        self._last_status = status
        is_running = status.get("is_running", False)
        is_paused = status.get("is_paused", False)
        pct = status.get("progress_percent", 0)
        has_error = status.get("has_error", False)

        # 1. Update each provider card first so it computes its own state & percentage
        for card in self.scraper_cards:
            card.update_status(status)

        arrow = "▶" if self.drawer_panel.isVisible() else "◀"

        # 2. Update Persistent Edge Tab header button
        if has_error:
            self.btn_toggle_drawer.setText(f"🔴 Sites {arrow}")
            self._style_toggle_button("ERROR")
        elif is_paused:
            self.btn_toggle_drawer.setText(f"⏸️ Sites ({pct}%) {arrow}")
            self._style_toggle_button("PAUSED")
        elif is_running:
            self.btn_toggle_drawer.setText(f"🔵 Sites ({pct}%) {arrow}")
            self._style_toggle_button("RUNNING")
        else:
            self.btn_toggle_drawer.setText(f"🛰️ Sites {arrow}")
            self._style_toggle_button("OK")

        # 3. Update individual edge pills per platform
        self._update_single_edge_pill(self.tab_curseforge_pill, "CurseForge", self.cf_card)
        self._update_single_edge_pill(self.tab_tsr_pill, "TSR", self.tsr_card)
        self._update_single_edge_pill(self.tab_modthesims_pill, "ModTheSims", self.mts_card)
        self._update_single_edge_pill(self.tab_simsfinds_pill, "SimsFinds", self.sf_card)
        self._update_single_edge_pill(self.tab_nexusmods_pill, "NexusMods", self.nexus_card)
        self._update_single_edge_pill(self.tab_mmccworld_pill, "MMCCWorld", self.mmccw_card)
        self._update_single_edge_pill(self.tab_loverslab_pill, "LoversLab", self.ll_card)
        self._update_single_edge_pill(self.tab_nsfwmods_pill, "NSFWMods", self.nm_card)

    def retranslate_ui(self):
        """Retranslates all static and dynamic UI texts according to current language."""
        self.d_title.setText(tr("drawer.title"))
        self.btn_toggle_drawer.setToolTip(tr("drawer.btn_toggle_tip"))
        self.tab_loverslab_pill.setToolTip(tr("drawer.pill_tip_ll"))
        self.tab_patreon_pill.setToolTip(tr("drawer.pill_tip_patreon"))
        for card in self.scraper_cards:
            card.retranslate_ui()
        self.patreon_card.retranslate_ui()

        if self._last_status:
            self.update_sync_status(self._last_status)
        else:
            arrow = "▶" if self.drawer_panel.isVisible() else "◀"
            self.btn_toggle_drawer.setText(f"🛰️ Sites {arrow}")

    def _style_toggle_button(self, state: str):
        if getattr(self, "_last_toggle_btn_state", None) == state:
            return
        self._last_toggle_btn_state = state
        self.btn_toggle_drawer.setStyleSheet(DrawerStyles.toggle_button(state))

    def _style_site_tab_pill(self, label: QLabel, state: str, text: str):
        label.setText(text)
        if not hasattr(self, "_last_tab_states"):
            self._last_tab_states = {}
        if self._last_tab_states.get(label) == state:
            return
        self._last_tab_states[label] = state
        label.setStyleSheet(DrawerStyles.site_tab_pill(state))
