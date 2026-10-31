"""Classe de base commune pour les cartes de mods (ModCard et InstalledCard).

Gère le conteneur de miniature, le cache mémoire LRU et le téléchargement/pré-décodage
asynchrone hors du thread principal Qt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel

from src.api.client import get_api_client
from src.core.config import AppConfig
from src.ui.components.image_cache import ImageCache
from src.utils.logger import logger


class ImageLoadSignals(QObject):
    """Signaux émis lors de la fin du téléchargement et décodage d'une miniature."""

    loaded = Signal(str, str)  # remote_id, local_path


class ImageDownloadTask(QRunnable):
    """Tâche asynchrone téléchargeant une miniature distante via l'API."""

    def __init__(self, source: str, remote_id: str, url: str, dest_path: Path, signals: ImageLoadSignals):
        super().__init__()
        self.source = source
        self.remote_id = remote_id
        self.url = url
        self.dest_path = dest_path
        self.signals = signals

    def run(self) -> None:
        """Télécharge la miniature et l'écrit dans le cache disque."""
        try:
            api_client = get_api_client()
            resp = api_client.client.get(
                "/api/catalog/thumbnail",
                params={"source": self.source, "remote_id": self.remote_id, "url": self.url},
                timeout=20.0,
            )
            if resp.status_code == 200 and len(resp.content) > 100:
                self.dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.dest_path, "wb") as f:
                    f.write(resp.content)
                self.signals.loaded.emit(self.remote_id, str(self.dest_path))
        except Exception as e:
            logger.debug(f"Thumbnail download failed via API for {self.url}: {e}")


class BaseModCard(QFrame):
    """Classe de base partagée par ModCard et InstalledCard."""

    details_requested = Signal(dict)

    def __init__(self, mod_data: dict, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.thumb_label: Optional[QLabel] = None
        self.thumb_width = 271
        self.thumb_height = 145
        self._placeholder_icon = "🎮"
        self.signals = ImageLoadSignals()
        self.signals.loaded.connect(self._on_image_loaded)

    def _create_thumbnail_container(self, height: int = 145, placeholder_icon: str = "🎮") -> QLabel:
        """Crée le QLabel standard d'aperçu de miniature avec fond sombre."""
        self._placeholder_icon = placeholder_icon
        label = QLabel()
        label.setFixedHeight(height)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            background-color: #0b0d17;
            border-radius: 10px;
            border: 1px solid #1a1e32;
            color: #64748b;
            font-size: 28px;
        """)
        label.setText(placeholder_icon)
        self.thumb_label = label
        self.thumb_height = height
        return label

    def _reset_thumbnail_placeholder(self) -> None:
        """Réinitialise l'aperçu de miniature avant le chargement d'un nouveau mod recyclé."""
        if self.thumb_label:
            self.thumb_label.setPixmap(QPixmap())
            self.thumb_label.setText(self._placeholder_icon)

    def _load_thumbnail_async(self) -> None:
        """Vérifie le cache mémoire/disque ou planifie un téléchargement asynchrone."""
        thumb_url = self.mod_data.get("thumbnail_url", "")
        if not thumb_url:
            self._reset_thumbnail_placeholder()
            return

        scaled_pix = ImageCache.get_or_scale(thumb_url, self.thumb_width, self.thumb_height)
        if scaled_pix:
            if self.thumb_label:
                self.thumb_label.setPixmap(scaled_pix)
                self.thumb_label.setText("")
            return

        source = self.mod_data.get("source", "loverslab")
        remote_id = str(self.mod_data.get("remote_id", "unknown"))
        cache_name = f"thumb_{source}_{remote_id}.jpg"
        cache_path = AppConfig.get_thumbnails_cache_dir() / cache_name

        if cache_path.exists() and cache_path.stat().st_size > 100:
            self._display_image(str(cache_path))
        else:
            self._reset_thumbnail_placeholder()
            task = ImageDownloadTask(source, remote_id, thumb_url, cache_path, self.signals)
            QThreadPool.globalInstance().start(task)

    def _on_image_loaded(self, remote_id: str, local_path: str) -> None:
        """Callback déclenché lorsque ImageDownloadTask a terminé le téléchargement."""
        if str(self.mod_data.get("remote_id")) == remote_id:
            self._display_image(local_path)

    def _display_image(self, image_path: str) -> None:
        """Décode via QImage, redimensionne et met en cache la miniature."""
        qimg = QImage(image_path)
        if not qimg.isNull():
            thumb_url = self.mod_data.get("thumbnail_url", "")
            scaled_qimg = qimg.scaled(
                self.thumb_width,
                self.thumb_height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pixmap = QPixmap.fromImage(qimg)
            scaled = QPixmap.fromImage(scaled_qimg)
            if thumb_url:
                ImageCache.set(thumb_url, pixmap)
                ImageCache.set_scaled(thumb_url, self.thumb_width, self.thumb_height, scaled)
            if self.thumb_label:
                self.thumb_label.setPixmap(scaled)
                self.thumb_label.setText("")
