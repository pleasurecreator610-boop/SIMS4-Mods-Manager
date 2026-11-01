from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import Signal, Qt
from src.core.config import AppConfig
from src.core.provider_metadata import PROVIDER_SPECS
from src.utils.mod_type_classifier import ModTypeClassifier
from src.i18n import I18nManager, tr


class FilterBar(QWidget):
    """Modern filter bar with search, multi-criteria selectors, and +18 adult toggle with i18n support."""

    filters_changed = Signal()
    adult_content_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._adult_enabled: bool = AppConfig.load().adult_content_enabled
        self.init_ui()
        I18nManager.instance().language_changed.connect(lambda _: self.retranslate_ui())

    def init_ui(self):
        """Exécute l'opération init ui."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(10)

        # Search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("catalog.search_placeholder"))
        self.search_input.textChanged.connect(self._on_control_changed)
        layout.addWidget(self.search_input, stretch=2)

        # Source Combo
        self.source_combo = QComboBox()
        layout.addWidget(self.source_combo)

        # Mod Type Combo (Taxonomie générique multi-sources)
        self.type_combo = QComboBox()
        layout.addWidget(self.type_combo)

        # Access / State Combo (État du mod)
        self.access_combo = QComboBox()
        layout.addWidget(self.access_combo)

        # Install Status Combo (Statut d'installation)
        self.status_combo = QComboBox()
        layout.addWidget(self.status_combo)

        # Sort Combo
        self.sort_combo = QComboBox()
        layout.addWidget(self.sort_combo)

        # Quick +18 Adult Content Toggle Button (disabled by default)
        self.adult_toggle_btn = QPushButton("🔞 +18")
        self.adult_toggle_btn.setCheckable(True)
        self.adult_toggle_btn.setChecked(self._adult_enabled)
        self.adult_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_adult_toggle_btn()
        self.adult_toggle_btn.clicked.connect(self._on_adult_btn_clicked)
        layout.addWidget(self.adult_toggle_btn)

        self.retranslate_ui()

        self.source_combo.currentIndexChanged.connect(self._on_control_changed)
        self.type_combo.currentIndexChanged.connect(self._on_control_changed)
        self.access_combo.currentIndexChanged.connect(self._on_control_changed)
        self.status_combo.currentIndexChanged.connect(self._on_control_changed)
        self.sort_combo.currentIndexChanged.connect(self._on_control_changed)

    def _style_adult_toggle_btn(self):
        if self._adult_enabled:
            self.adult_toggle_btn.setText("🔞 +18 : ON")
            self.adult_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #7f1d1d;
                    color: #fecaca;
                    border: 1px solid #ef4444;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #991b1b; color: #ffffff; }
            """)
        else:
            self.adult_toggle_btn.setText("🔞 +18 : OFF")
            self.adult_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #64748b;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #334155; color: #cbd5e1; }
            """)

    def _on_adult_btn_clicked(self, checked: bool):
        self.set_adult_content_enabled(checked)
        self.adult_content_toggled.emit(checked)
        self.filters_changed.emit()

    def set_adult_content_enabled(self, enabled: bool):
        """Updates the +18 toggle button state and refreshes available sources in source_combo."""
        self._adult_enabled = bool(enabled)
        self.adult_toggle_btn.blockSignals(True)
        self.adult_toggle_btn.setChecked(self._adult_enabled)
        self.adult_toggle_btn.blockSignals(False)
        self._style_adult_toggle_btn()
        self._populate_source_combo()

    def _populate_source_combo(self):
        src_curr = self.source_combo.currentData() or "all"
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItem(tr("catalog.filter_provider_all"), "all")
        for spec in PROVIDER_SPECS.values():
            if not spec.in_catalog_filter:
                continue
            if spec.is_adult and not self._adult_enabled:
                continue
            self.source_combo.addItem(spec.filter_label, spec.filter_data)
        idx = self.source_combo.findData(src_curr)
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)
        else:
            self.source_combo.setCurrentIndex(0)
        self.source_combo.blockSignals(False)

    def retranslate_ui(self):
        """Populates or retranslates all combo box items while keeping selected values."""
        self.search_input.setPlaceholderText(tr("catalog.search_placeholder"))
        self.adult_toggle_btn.setToolTip(tr("filter_bar.adult_toggle_tip"))
        self._style_adult_toggle_btn()

        # 1. Source combo
        self._populate_source_combo()

        # 2. Type combo
        type_curr = self.type_combo.currentData() or "all"
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        for t_id, label in ModTypeClassifier.get_type_choices():
            self.type_combo.addItem(label, userData=t_id)
        idx = self.type_combo.findData(type_curr)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.blockSignals(False)

        # 3. Access combo
        acc_curr = self.access_combo.currentData() or "all"
        self.access_combo.blockSignals(True)
        self.access_combo.clear()
        self.access_combo.addItem(tr("filter_bar.all_access"), "all")
        self.access_combo.addItem(tr("filter_bar.access_direct"), "direct")
        self.access_combo.addItem(tr("filter_bar.access_needs_account"), "needs_account")
        self.access_combo.addItem(tr("filter_bar.access_needs_sub"), "needs_sub")
        self.access_combo.addItem(tr("filter_bar.access_unlocked"), "unlocked")
        idx = self.access_combo.findData(acc_curr)
        if idx >= 0:
            self.access_combo.setCurrentIndex(idx)
        self.access_combo.blockSignals(False)

        # 4. Status combo
        stat_curr = self.status_combo.currentData() or "all"
        self.status_combo.blockSignals(True)
        self.status_combo.clear()
        self.status_combo.addItem(tr("filter_bar.all_statuses"), "all")
        self.status_combo.addItem(tr("filter_bar.status_not_installed"), "not_installed")
        self.status_combo.addItem(tr("filter_bar.status_installed"), "installed")
        self.status_combo.addItem(tr("filter_bar.status_updates_available"), "updates_available")
        idx = self.status_combo.findData(stat_curr)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.status_combo.blockSignals(False)

        # 5. Sort combo
        sort_curr = self.sort_combo.currentData() or "recent"
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        self.sort_combo.addItem(tr("catalog.sort_updated"), "recent")
        self.sort_combo.addItem(tr("catalog.sort_alpha"), "az")
        idx = self.sort_combo.findData(sort_curr)
        if idx >= 0:
            self.sort_combo.setCurrentIndex(idx)
        self.sort_combo.blockSignals(False)

    def _on_control_changed(self, *args):
        """Emits filters_changed regardless of any arguments passed by widget signals."""
        self.filters_changed.emit()

    def reset_filters(self):
        """Resets all filter controls to their default states."""
        self.search_input.clear()
        self.source_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.access_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.sort_combo.setCurrentIndex(0)

    def get_filter_state(self) -> dict:
        """Returns the current filter parameters as a dict with robust data keys."""
        return {
            "search": self.search_input.text().strip().lower(),
            "source": self.source_combo.currentData() or self.source_combo.currentText(),
            "mod_type": self.type_combo.currentData() or "all",
            "access": self.access_combo.currentData() or self.access_combo.currentText(),
            "status": self.status_combo.currentData() or self.status_combo.currentText(),
            "sort": self.sort_combo.currentData() or self.sort_combo.currentText(),
            "include_adult": self._adult_enabled,
        }
