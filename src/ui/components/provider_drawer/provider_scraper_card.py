"""
ProviderScraperDrawerCard:
Encapsulates detailed scraping controls, subcategories, and progress for any catalog provider
(CurseForge, The Sims Resource, ModTheSims, SimsFinds, Nexus Mods, MMCCWorld, LoversLab, NSFWMods).
"""

from typing import Dict, Any, Tuple, Optional, List
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QProgressBar,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal

from src.i18n import tr
from src.ui.components.provider_drawer.drawer_styles import DrawerStyles
from src.ui.components.provider_drawer.subcategory_row import SubcategoryRowWidget


LOVERSLAB_SUBCATS: List[Tuple[str, str, str]] = [
    ("174", "WickedWhims", "🔞"),
    ("201", "Animations : WickedWhims", "💃"),
    ("215", "Translations : WickedWhims", "🌐"),
    ("202", "Animations : Other", "🎬"),
    ("200", "Extensions", "🧩"),
    ("203", "Clothing", "👗"),
    ("204", "Accessories & Makeup", "💄"),
    ("205", "Body Parts", "✨"),
    ("206", "Objects", "🛋️"),
    ("404", "Paintings & Posters", "🖼️"),
    ("207", "Lots", "🏡"),
    ("209", "Translations", "🌐"),
    ("210", "Other", "📦"),
    ("216", "Uncategorized", "📁"),
]

NSFWMODS_SUBCATS: List[Tuple[str, str, str]] = [
    ("nsfwmods_287", "Sims Mods (Main)", "🔞"),
    ("nsfwmods_364", "Adult (NSFWMods)", "🔥"),
    ("nsfwmods_289", "Clothing", "👗"),
    ("nsfwmods_296", "Shoes", "👠"),
    ("nsfwmods_292", "Accessories", "💍"),
    ("nsfwmods_288", "Body Types", "✨"),
    ("nsfwmods_290", "Hair", "💇"),
    ("nsfwmods_294", "Skintones", "✨"),
    ("nsfwmods_295", "Facial Hair", "🧔"),
    ("nsfwmods_291", "Makeup", "💄"),
    ("nsfwmods_293", "Eyes", "👁️"),
]

CURSEFORGE_SUBCATS: List[Tuple[str, str, str]] = [
    ("cf_mods_gameplay", "Mods : Gameplay", "🎮"),
    ("cf_mods_utilities", "Mods : Utilities", "🛠️"),
    ("cf_mods_poses", "Poses & Animations", "💃"),
    ("cf_create_a_sim", "Create a Sim (CAS)", "👗"),
    ("cf_build_buy", "Build / Buy", "🛋️"),
    ("cf_rooms_lots", "Rooms & Lots", "🏡"),
    ("cf_sims_households", "Sims & Households", "👥"),
    ("cf_worlds", "Worlds", "🌍"),
    ("cf_translations", "Translations", "🌐"),
]

TSR_SUBCATS: List[Tuple[str, str, str]] = [
    ("tsr_mods", "Mods (TSR)", "🧩"),
    ("tsr_clothing", "Clothing", "👗"),
    ("tsr_hair", "Hair", "💇"),
    ("tsr_shoes", "Shoes", "👠"),
    ("tsr_accessories", "Accessories", "💍"),
    ("tsr_makeup", "Makeup", "💄"),
    ("tsr_skintones", "Skintones", "✨"),
    ("tsr_eyecolors", "Eye Colors", "👁️"),
    ("tsr_objects", "Objects", "🛋️"),
    ("tsr_sets", "Sets", "📦"),
    ("tsr_lots_rooms", "Lots & Rooms", "🏡"),
    ("tsr_sims", "Sims", "👤"),
]

MODTHESIMS_SUBCATS: List[Tuple[str, str, str]] = [
    ("mts_game_mods", "Game Mods", "🎮"),
    ("mts_traits", "Traits", "🎓"),
    ("mts_careers", "Careers", "💼"),
    ("mts_build_mode", "Build Mode", "🧱"),
    ("mts_buy_mode", "Buy Mode", "🛋️"),
    ("mts_body_shop", "Body Shop", "👗"),
    ("mts_lots_housing", "Lots & Housing", "🏡"),
    ("mts_sims", "Sims", "👤"),
    ("mts_pets", "Pets", "🐾"),
    ("mts_programs_utilities", "Programs & Utilities", "🛠️"),
    ("mts_miscellaneous", "Miscellaneous", "📦"),
]

SIMSFINDS_SUBCATS: List[Tuple[str, str, str]] = [
    ("sfinds_hairstyles", "Hairstyles", "💇"),
    ("sfinds_clothing", "Clothing", "👗"),
    ("sfinds_accessories", "Accessories", "💍"),
    ("sfinds_shoes", "Shoes", "👠"),
    ("sfinds_makeup", "Makeup", "💄"),
    ("sfinds_skintones", "Skintones", "✨"),
    ("sfinds_eyebrows", "Eyebrows", "👁️"),
    ("sfinds_objects", "Objects", "🛋️"),
    ("sfinds_build_mode", "Build Mode", "🧱"),
    ("sfinds_mods", "Mods & Presets", "🎮"),
    ("sfinds_sims", "Sims", "👤"),
]

NEXUSMODS_SUBCATS: List[Tuple[str, str, str]] = [
    ("nexus_gameplay", "Gameplay", "🎮"),
    ("nexus_utilities", "Utilities", "🛠️"),
    ("nexus_user_interface", "UI Mods", "🖥️"),
    ("nexus_clothing", "Clothing", "👗"),
    ("nexus_cas", "Create a Sim", "💇"),
    ("nexus_build_mode", "Build Mode", "🧱"),
    ("nexus_buy_mode", "Buy Mode", "🛋️"),
    ("nexus_decorations", "Decorations", "🖼️"),
    ("nexus_careers", "Careers & Traits", "💼"),
    ("nexus_miscellaneous", "Miscellaneous", "📦"),
]

MMCCWORLD_SUBCATS: List[Tuple[str, str, str]] = [
    ("mmccw_clothing", "Clothing", "👗"),
    ("mmccw_hair", "Hairstyles", "💇"),
    ("mmccw_accessories", "Accessories", "💍"),
    ("mmccw_shoes", "Shoes", "👠"),
    ("mmccw_build_buy", "Build & Buy", "🛋️"),
    ("mmccw_gameplay", "Gameplay & Mods", "🎮"),
    ("mmccw_poses", "Poses & Animations", "💃"),
    ("mmccw_miscellaneous", "Recent Finds", "📦"),
]

DEADERPOOL_SUBCATS: List[Tuple[str, str, str]] = [
    ("dp_mccc_core", "MC Command Center", "⚙️"),
    ("dp_mc_woohoo", "MC WooHoo", "💞"),
]

SCUMBUMBO_SUBCATS: List[Tuple[str, str, str]] = [
    ("scumbumbo_core", "XML Injector & Core", "🧬"),
    ("scumbumbo_gameplay", "Gameplay Mods", "🎮"),
]

LUMPINOU_SUBCATS: List[Tuple[str, str, str]] = [
    ("lumpinou_core", "Mood Pack & Toolbox", "🧰"),
    ("lumpinou_overhauls", "RPO & Overhauls", "🤰"),
]

WICKEDCC_SUBCATS: List[Tuple[str, str, str]] = [
    ("wickedcc_core", "WickedWhims & Wonderful", "🔞"),
    ("wickedcc_animations", "Official Animations", "💃"),
    ("wickedcc_body_skins", "Skins & Anatomy", "✨"),
]

BASEMENTAL_SUBCATS: List[Tuple[str, str, str]] = [
    ("basemental_adult", "Drugs & Gangs (+18)", "🔞"),
    ("basemental_utilities", "Universal Venue List", "🏢"),
]

GAMEBANANA_SUBCATS: List[Tuple[str, str, str]] = [
    ("gb_mods_gameplay", "Gameplay & Scripts", "🎮"),
    ("gb_skins_cas", "Skins & CAS", "👗"),
    ("gb_ui_sounds", "UI & Sounds", "🎵"),
]

THESIMSCATALOG_SUBCATS: List[Tuple[str, str, str]] = [
    ("tsc_hairstyles", "Hairstyles", "💇"),
    ("tsc_clothing", "Clothing", "👗"),
    ("tsc_furniture", "Furniture", "🛋️"),
    ("tsc_mods", "Game Mods", "🎮"),
]

ITCHIO_SUBCATS: List[Tuple[str, str, str]] = [
    ("itchio_game_mods", "Game Mods", "🎮"),
    ("itchio_cc_packs", "Stuff Packs & CC", "📦"),
]

SIMS4STUDIO_SUBCATS: List[Tuple[str, str, str]] = [
    ("s4s_andrews_studio", "Andrew's Studio (Pose Player)", "🎬"),
    ("s4s_creator_studios", "Creator Studios", "🎨"),
    ("s4s_poses_animations", "Poses & Animations", "💃"),
]

LITTLEMSSAM_SUBCATS: List[Tuple[str, str, str]] = [
    ("lms_gameplay_mods", "Big Gameplay Mods", "🎮"),
    ("lms_random_small_mods", "Random Small Mods", "🧩"),
]

SIXAMCC_SUBCATS: List[Tuple[str, str, str]] = [
    ("sixam_furniture_packs", "Furniture Packs", "🛋️"),
    ("sixam_build_decor", "Build & Clutter", "🧱"),
]

SYNTHIRA_SUBCATS: List[Tuple[str, str, str]] = [
    ("synthira_adult_mods", "Adult Mods +18", "🔞"),
    ("synthira_gameplay_mods", "Gameplay Mods", "🎮"),
    ("synthira_clothing_cas", "Clothing & CAS", "👗"),
]

F95ZONE_SUBCATS: List[Tuple[str, str, str]] = [
    ("f95_sims4_mods", "Sims 4 Adult Mods", "🔞"),
    ("f95_sims4_animations", "WW Megapacks", "💃"),
]

SMUTBASE_SUBCATS: List[Tuple[str, str, str]] = [
    ("smutbase_rigs_meshes", "Meshes & Anatomy Rigs", "✨"),
    ("smutbase_props_furniture", "Interactive Props", "🛋️"),
]


class ProviderScraperDrawerCard(QFrame):
    """Encapsulates the detailed scraping controls, subcategories, and progress for a mod provider."""

    start_requested = Signal(str)
    pause_requested = Signal(str)
    resume_requested = Signal(str)
    stop_requested = Signal(str)

    def __init__(
        self,
        provider_name: str = "loverslab",
        display_name: str = "LoversLab",
        subcategories_meta: Optional[List[Tuple[str, str, str]]] = None,
        expanded_by_default: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.provider_name = provider_name.lower()
        self.display_name = display_name
        self._subcategories_meta = subcategories_meta or LOVERSLAB_SUBCATS
        self._ll_is_expanded = expanded_by_default
        self.subcat_widgets: Dict[str, SubcategoryRowWidget] = {}
        self.subcat_rows: Dict[str, Tuple[QLabel, QLabel, QLabel]] = {}
        self._current_is_paused = False
        self.last_computed_pct = 0
        self.last_computed_state = "OK"
        self._init_ui()

    def _init_ui(self):
        frame_id = f"drawer_card_{self.provider_name}"
        self.setObjectName(frame_id)
        self.setStyleSheet(f"""
            QFrame#{frame_id} {{
                background-color: #13172e;
                border: 1px solid #222d52;
                border-radius: 8px;
            }}
            QFrame#{frame_id} QLabel {{
                background-color: transparent;
                border: none;
                padding: 0px;
            }}
        """)
        ll_layout = QVBoxLayout(self)
        ll_layout.setContentsMargins(10, 10, 10, 10)
        ll_layout.setSpacing(8)

        # Header
        ll_header = QHBoxLayout()
        ll_name = QLabel(self.display_name)
        ll_name.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        ll_header.addWidget(ll_name)
        ll_header.addStretch()

        self.drawer_status_pill = QLabel(tr("drawer.status_ready"))
        self._style_status_pill("OK", tr("drawer.status_ready"))
        ll_header.addWidget(self.drawer_status_pill)

        self.btn_collapse_ll = QPushButton("▼" if self._ll_is_expanded else "▲")
        self.btn_collapse_ll.setFixedSize(20, 20)
        self.btn_collapse_ll.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_collapse_ll.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { color: #f8fafc; }
        """)
        self.btn_collapse_ll.clicked.connect(self._toggle_loverslab_section)
        ll_header.addWidget(self.btn_collapse_ll)
        ll_layout.addLayout(ll_header)

        # Collapsed Summary
        self.ll_collapsed_summary = QWidget()
        cs_layout = QVBoxLayout(self.ll_collapsed_summary)
        cs_layout.setContentsMargins(0, 2, 0, 2)
        cs_layout.setSpacing(4)
        self.ll_collapsed_summary_lbl = QLabel(f"{len(self._subcategories_meta)} sous-catégories • 0 mods")
        self.ll_collapsed_summary_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        cs_layout.addWidget(self.ll_collapsed_summary_lbl)
        self.ll_collapsed_summary.setVisible(not self._ll_is_expanded)
        ll_layout.addWidget(self.ll_collapsed_summary)

        # Expanded Details
        self.ll_expanded_details = QWidget()
        ed_layout = QVBoxLayout(self.ll_expanded_details)
        ed_layout.setContentsMargins(0, 0, 0, 0)
        ed_layout.setSpacing(6)

        self.drawer_progress_bar = QProgressBar()
        self.drawer_progress_bar.setFixedHeight(8)
        self.drawer_progress_bar.setRange(0, 100)
        self.drawer_progress_bar.setValue(0)
        self.drawer_progress_bar.setTextVisible(False)
        self.drawer_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0a0e1c;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 4px;
            }
        """)
        ed_layout.addWidget(self.drawer_progress_bar)

        self.drawer_lbl_progress = QLabel(tr("drawer.progress", done=0, total=0, pct=0))
        self.drawer_lbl_progress.setStyleSheet("font-size: 11px; color: #cbd5e1; font-weight: 600;")
        ed_layout.addWidget(self.drawer_lbl_progress)

        self.drawer_lbl_category = QLabel(tr("drawer.category_current", cat=tr("common.ready")))
        self.drawer_lbl_category.setStyleSheet("font-size: 11px; color: #94a3b8;")
        ed_layout.addWidget(self.drawer_lbl_category)

        self.drawer_lbl_mods = QLabel(tr("drawer.mods_count", count=0))
        self.drawer_lbl_mods.setStyleSheet("font-size: 11px; color: #94a3b8;")
        ed_layout.addWidget(self.drawer_lbl_mods)

        self.drawer_lbl_last_sync = QLabel(tr("drawer.last_scan", time=tr("common.pending")))
        self.drawer_lbl_last_sync.setStyleSheet("font-size: 10px; color: #64748b;")
        ed_layout.addWidget(self.drawer_lbl_last_sync)

        # Subcategories
        self.lbl_subcats = QLabel(f"Sous-catégories ({len(self._subcategories_meta)}) :")
        self.lbl_subcats.setStyleSheet("font-size: 11px; font-weight: 700; color: #60a5fa; margin-top: 4px;")
        ed_layout.addWidget(self.lbl_subcats)

        subcats_scroll = QScrollArea()
        subcats_scroll.setFixedHeight(145)
        subcats_scroll.setWidgetResizable(True)
        subcats_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0a0d1c;
                border: 1px solid #1a223e;
                border-radius: 6px;
            }
        """)
        self.subcats_container = QWidget()
        self.subcats_layout = QVBoxLayout(self.subcats_container)
        self.subcats_layout.setContentsMargins(6, 6, 6, 6)
        self.subcats_layout.setSpacing(4)
        subcats_scroll.setWidget(self.subcats_container)
        ed_layout.addWidget(subcats_scroll)

        self._init_subcategory_rows()

        # Scraping Action Controls
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setSpacing(6)

        self.btn_resync = QPushButton(f"🔄 Relancer {self.display_name}")
        self.btn_resync.setFixedHeight(30)
        self.btn_resync.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_resync.setStyleSheet(DrawerStyles.resync_button(False))
        self.btn_resync.clicked.connect(lambda: self.start_requested.emit(self.provider_name))
        ctrl_layout.addWidget(self.btn_resync)

        btn_sub_row = QHBoxLayout()
        btn_sub_row.setSpacing(6)

        self.btn_pause_resume = QPushButton(tr("drawer.btn_pause"))
        self.btn_pause_resume.setFixedHeight(28)
        self.btn_pause_resume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause_resume.setStyleSheet(DrawerStyles.pause_button(False, disabled=True))
        self.btn_pause_resume.setEnabled(False)
        self.btn_pause_resume.clicked.connect(self._on_pause_resume_clicked)
        btn_sub_row.addWidget(self.btn_pause_resume, stretch=1)

        self.btn_stop = QPushButton(tr("drawer.btn_stop"))
        self.btn_stop.setFixedHeight(28)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setStyleSheet(DrawerStyles.stop_button(disabled=True))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(lambda: self.stop_requested.emit(self.provider_name))
        btn_sub_row.addWidget(self.btn_stop, stretch=1)

        ctrl_layout.addLayout(btn_sub_row)
        ed_layout.addLayout(ctrl_layout)

        self.ll_expanded_details.setVisible(self._ll_is_expanded)
        ll_layout.addWidget(self.ll_expanded_details)

    def _init_subcategory_rows(self):
        for cid, cname, cicon in self._subcategories_meta:
            row_widget = SubcategoryRowWidget(cid, cname, cicon, parent=self.subcats_container)
            self.subcats_layout.addWidget(row_widget)
            self.subcat_widgets[cid] = row_widget
            self.subcat_rows[cid] = row_widget.labels_tuple

    def _toggle_loverslab_section(self):
        self._ll_is_expanded = not self._ll_is_expanded
        self.ll_expanded_details.setVisible(self._ll_is_expanded)
        self.ll_collapsed_summary.setVisible(not self._ll_is_expanded)
        self.btn_collapse_ll.setText("▼" if self._ll_is_expanded else "▲")

    def _on_pause_resume_clicked(self):
        if self._current_is_paused:
            self.resume_requested.emit(self.provider_name)
        else:
            self.pause_requested.emit(self.provider_name)

    def _style_status_pill(self, state: str, text: Optional[str] = None):
        if text:
            self.drawer_status_pill.setText(text)
        self.drawer_status_pill.setStyleSheet(DrawerStyles.status_pill(state))

    def _resolve_subcat_widget(self, cid: str) -> Optional[SubcategoryRowWidget]:
        """Resolves subcategory widget supporting exact IDs, stripped IDs, and provider prefixes."""
        if cid in self.subcat_widgets:
            return self.subcat_widgets[cid]
        candidates = [
            f"{self.provider_name}_{cid}",
            cid.replace(f"{self.provider_name}_", ""),
            cid.replace("nsfwmods_", "nm_"),
            cid.replace("nm_", "nsfwmods_"),
        ]
        for cand in candidates:
            if cand in self.subcat_widgets:
                return self.subcat_widgets[cand]
        return None

    def update_status(self, status: Dict[str, Any]):
        """Updates provider-specific progress bar, subcategory rows, and control buttons."""
        global_running = status.get("is_running", False)
        global_paused = status.get("is_paused", False)
        global_stopped = status.get("is_stopped", False)
        has_error = status.get("has_error", False)
        last_completed = status.get("last_completed_at") or ""
        categories_progress = status.get("categories_progress", [])
        providers_status = status.get("providers_status", {}) or {}

        prov_state_str = providers_status.get(self.provider_name, "")

        # Extract subcategories belonging to this provider
        my_cats = []
        for cat_info in categories_progress:
            cid = str(cat_info.get("id") if isinstance(cat_info, dict) else getattr(cat_info, "id", ""))
            if self._resolve_subcat_widget(cid) is not None:
                my_cats.append(cat_info)

        if my_cats:
            pages_done = sum(
                (c.get("pages_completed", 0) if isinstance(c, dict) else getattr(c, "pages_completed", 0))
                for c in my_cats
            )
            total_pages = sum(
                (c.get("total_pages", 0) if isinstance(c, dict) else getattr(c, "total_pages", 0)) for c in my_cats
            )
            total_scraped = sum(
                (c.get("mods_count", 0) if isinstance(c, dict) else getattr(c, "mods_count", 0)) for c in my_cats
            )
            pct = int((pages_done / total_pages) * 100) if total_pages > 0 else 0
            in_prog = [
                (c.get("name", "") if isinstance(c, dict) else getattr(c, "name", ""))
                for c in my_cats
                if (c.get("status") if isinstance(c, dict) else getattr(c, "status", "")) == "IN_PROGRESS"
            ]
            any_in_prog = len(in_prog) > 0
            all_completed = all(
                (c.get("status") if isinstance(c, dict) else getattr(c, "status", "")) == "COMPLETED" for c in my_cats
            )
            cur_cat = in_prog[0] if in_prog else (tr("common.completed") if all_completed else tr("common.ready"))
            is_paused = global_paused and (prov_state_str == "PAUSED" or any_in_prog)
            is_running = (
                global_running and not is_paused and (prov_state_str == "RUNNING" or any_in_prog) and not all_completed
            )
            is_stopped = global_stopped or prov_state_str == "STOPPED"
        else:
            is_paused = global_paused
            is_running = global_running and (
                not providers_status or prov_state_str == "RUNNING" or self.provider_name == "loverslab"
            )
            is_stopped = global_stopped
            pct = status.get("progress_percent", 0) if is_running or is_paused else 0
            pages_done = status.get("pages_completed", 0) if is_running or is_paused else 0
            total_pages = status.get("total_pages", 0) if is_running or is_paused else 0
            cur_cat = (status.get("current_category") or tr("common.ready")) if is_running else tr("common.ready")
            total_scraped = status.get("total_scraped", 0) if self.provider_name == "loverslab" else 0

        self._current_is_paused = is_paused
        self.last_computed_pct = pct

        if has_error and prov_state_str == "ERROR":
            self.last_computed_state = "ERROR"
            self._style_status_pill("ERROR", tr("drawer.status_error"))
        elif is_paused:
            self.last_computed_state = "PAUSED"
            self._style_status_pill("PAUSED", f"{tr('drawer.status_paused')} ({pct}%)")
        elif is_running:
            self.last_computed_state = "RUNNING"
            self._style_status_pill("RUNNING", f"{tr('drawer.status_running')} ({pct}%)")
        elif is_stopped:
            self.last_computed_state = "STOPPED"
            self._style_status_pill("STOPPED", tr("drawer.status_stopped"))
        else:
            self.last_computed_state = "OK"
            self._style_status_pill("OK", tr("drawer.status_ready"))

        self.drawer_progress_bar.setValue(pct)
        self.drawer_lbl_progress.setText(tr("drawer.progress", done=pages_done, total=total_pages, pct=pct))
        self.drawer_lbl_category.setText(tr("drawer.category_current", cat=cur_cat))
        self.drawer_lbl_mods.setText(tr("drawer.mods_count", count=total_scraped))
        if last_completed:
            self.drawer_lbl_last_sync.setText(tr("drawer.last_scan", time=last_completed))

        self.ll_collapsed_summary_lbl.setText(
            f"{cur_cat} • {pct}% ({total_scraped} mods)"
            if is_running or is_paused
            else f"{len(self._subcategories_meta)} sous-catégories • {total_scraped} mods"
        )

        if is_paused:
            self.btn_resync.setText(tr("drawer.btn_paused"))
            self.btn_resync.setEnabled(False)
            self.btn_resync.setStyleSheet(DrawerStyles.resync_button(is_paused=True))

            self.btn_pause_resume.setText(tr("drawer.btn_resume"))
            self.btn_pause_resume.setEnabled(True)
            self.btn_pause_resume.setStyleSheet(DrawerStyles.pause_button(is_paused=True))

            self.btn_stop.setEnabled(True)
            self.btn_stop.setStyleSheet(DrawerStyles.stop_button(disabled=False))
        elif is_running:
            self.btn_resync.setText(tr("drawer.btn_in_progress"))
            self.btn_resync.setEnabled(False)
            self.btn_resync.setStyleSheet(DrawerStyles.resync_button(loading=True))

            self.btn_pause_resume.setText(tr("drawer.btn_pause"))
            self.btn_pause_resume.setEnabled(True)
            self.btn_pause_resume.setStyleSheet(DrawerStyles.pause_button(is_paused=False))

            self.btn_stop.setEnabled(True)
            self.btn_stop.setStyleSheet(DrawerStyles.stop_button(disabled=False))
        else:
            self.btn_resync.setText(f"🔄 Relancer {self.display_name}")
            self.btn_resync.setEnabled(True)
            self.btn_resync.setStyleSheet(DrawerStyles.resync_button(loading=False))

            self.btn_pause_resume.setText(tr("drawer.btn_pause"))
            self.btn_pause_resume.setEnabled(False)
            self.btn_pause_resume.setStyleSheet(DrawerStyles.pause_button(disabled=True))

            self.btn_stop.setEnabled(False)
            self.btn_stop.setStyleSheet(DrawerStyles.stop_button(disabled=True))

        for cat_info in my_cats:
            cid = str(cat_info.get("id") if isinstance(cat_info, dict) else getattr(cat_info, "id", ""))
            row_widget = self._resolve_subcat_widget(cid)
            if not row_widget:
                continue

            status_val = (
                cat_info.get("status") if isinstance(cat_info, dict) else getattr(cat_info, "status", "PENDING")
            )
            p_done = (
                cat_info.get("pages_completed", 0)
                if isinstance(cat_info, dict)
                else getattr(cat_info, "pages_completed", 0)
            )
            p_total = (
                cat_info.get("total_pages", 0) if isinstance(cat_info, dict) else getattr(cat_info, "total_pages", 0)
            )
            m_cnt = cat_info.get("mods_count", 0) if isinstance(cat_info, dict) else getattr(cat_info, "mods_count", 0)

            if status_val == "COMPLETED":
                row_widget.set_status(f"Terminé ({m_cnt} mods)", "#34d399")
            elif status_val == "IN_PROGRESS":
                row_widget.set_status(f"p.{p_done}/{p_total} ({m_cnt})", "#60a5fa")
            elif status_val == "STOPPED":
                row_widget.set_status(f"Arrêté ({p_done}/{p_total})", "#f59e0b")
            elif status_val == "ERROR":
                row_widget.set_status("Erreur", "#f87171")
            else:
                row_widget.set_status("Attente", "#64748b")

    def retranslate_ui(self):
        """Exécute l'opération retranslate ui."""
        self.lbl_subcats.setText(f"Sous-catégories ({len(self._subcategories_meta)}) :")
        self._style_status_pill("OK", tr("drawer.status_ready"))
        self.ll_collapsed_summary_lbl.setText(f"{len(self._subcategories_meta)} sous-catégories • 0 mods")
        self.drawer_lbl_progress.setText(tr("drawer.progress", done=0, total=0, pct=0))
        self.drawer_lbl_category.setText(tr("drawer.category_current", cat=tr("common.ready")))
        self.drawer_lbl_mods.setText(tr("drawer.mods_count", count=0))
        self.drawer_lbl_last_sync.setText(tr("drawer.last_scan", time=tr("common.pending")))
        self.btn_resync.setText(f"🔄 Relancer {self.display_name}")
        self.btn_pause_resume.setText(tr("drawer.btn_pause"))
        self.btn_stop.setText(tr("drawer.btn_stop"))
