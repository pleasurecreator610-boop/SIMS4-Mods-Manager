"""Grille responsive de cartes de mods avec support de recyclage d'instances (Object Pooling)."""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence
from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget


class ResponsiveCardGrid(QWidget):
    """Grille responsive réutilisable pour les cartes de mods.

    Adapte automatiquement le nombre de colonnes selon la largeur disponible
    et supporte le recyclage in-place des cartes (update_pool) sans détruire les widgets.
    """

    def __init__(
        self,
        min_card_width: int = 250,
        spacing: int = 14,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.min_card_width = max(120, min_card_width)
        self.grid_spacing = spacing
        self._cards: List[QWidget] = []
        self._pool: List[QWidget] = []
        self._current_columns = 4
        self._empty_label: Optional[QLabel] = None

        self._grid_layout = QGridLayout(self)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(self.grid_spacing)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    @property
    def cards(self) -> List[QWidget]:
        """Retourne les cartes actuellement actives dans la grille."""
        return self._cards

    @property
    def pool_size(self) -> int:
        """Retourne le nombre total de cartes conservées dans le pool mémoire."""
        return len(self._pool)

    def calculate_columns(self, available_width: int) -> int:
        """Calcule le nombre optimal de colonnes selon la largeur disponible."""
        if available_width <= 0:
            return 1
        effective_w = max(0, available_width - 14)
        cols = (effective_w + self.grid_spacing) // (self.min_card_width + self.grid_spacing)
        return max(1, cols)

    def _remove_empty_label(self) -> None:
        if self._empty_label is not None:
            self._grid_layout.removeWidget(self._empty_label)
            self._empty_label.deleteLater()
            self._empty_label = None

    def set_empty_message(self, message: str) -> None:
        """Affiche un message centré lorsqu'aucune carte n'est disponible tout en préservant le pool."""
        self._remove_empty_label()
        while self._grid_layout.count():
            self._grid_layout.takeAt(0)
        for card in self._pool:
            card.setVisible(False)
        self._cards.clear()

        self._empty_label = QLabel(message)
        self._empty_label.setStyleSheet("font-size: 14px; color: #64748b; padding: 40px;")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_layout.addWidget(self._empty_label, 0, 0)

    def update_pool(
        self,
        items_data: Sequence[Any],
        factory_fn: Callable[[Any], QWidget],
        update_fn: Callable[[QWidget, Any], None],
    ) -> List[QWidget]:
        """Recycle les cartes existantes du pool in-place et n'instancie que le différentiel nécessaire."""
        self._remove_empty_label()

        needed = len(items_data)
        for idx, item in enumerate(items_data):
            if idx < len(self._pool):
                card = self._pool[idx]
                update_fn(card, item)
                card.setVisible(True)
            else:
                card = factory_fn(item)
                self._pool.append(card)
                card.setVisible(True)

        for idx in range(needed, len(self._pool)):
            self._pool[idx].setVisible(False)

        self._cards = self._pool[:needed]

        available_w = self.width()
        if available_w > 50:
            self._current_columns = self.calculate_columns(available_w)
        self._re_layout()
        return self._cards

    def set_cards(self, cards: Sequence[QWidget]) -> None:
        """Remplace la collection de cartes par une nouvelle liste et réorganise la grille."""
        self.clear()
        self._cards = list(cards)
        self._pool = list(cards)

        available_w = self.width()
        if available_w > 50:
            self._current_columns = self.calculate_columns(available_w)
        self._re_layout()

    def add_card(self, card: QWidget) -> None:
        """Ajoute une carte individuelle à la grille."""
        self._remove_empty_label()

        self._cards.append(card)
        if card not in self._pool:
            self._pool.append(card)
        idx = len(self._cards) - 1
        row = idx // self._current_columns
        col = idx % self._current_columns
        self._grid_layout.addWidget(card, row, col)

    def clear(self) -> None:
        """Détache et détruit toutes les cartes et labels de la grille."""
        self._remove_empty_label()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item and item.widget():
                w = item.widget()
                if w:
                    w.deleteLater()
        for card in self._pool:
            card.deleteLater()
        self._cards.clear()
        self._pool.clear()

    def _re_layout(self) -> None:
        """Redistribue les widgets actifs sur les lignes et colonnes sans les détruire."""
        while self._grid_layout.count():
            self._grid_layout.takeAt(0)

        cols = max(1, self._current_columns)
        for idx, card in enumerate(self._cards):
            row = idx // cols
            col = idx % cols
            self._grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Recalcule dynamiquement la disposition lorsque la largeur change."""
        super().resizeEvent(event)
        new_w = event.size().width()
        new_cols = self.calculate_columns(new_w)
        if new_cols != self._current_columns and self._cards:
            self._current_columns = new_cols
            self._re_layout()
