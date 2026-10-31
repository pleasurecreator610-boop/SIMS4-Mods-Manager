"""Classe de base commune pour les cartes de mods (ModCard et InstalledCard).

Gère le conteneur de miniature, le cache mémoire LRU (uniquement QPixmap redimensionnés),
la déduplication in-flight des téléchargements et le décodage/redimensionnement QImage
100 % hors du thread principal Qt.
"""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel

from src.api.client import get_api_client
from src.core.config import AppConfig
from src.ui.components.image_cache import ImageCache
from src.utils.logger import logger


class ImageLoadSignals(QObject):
    """Signaux émis lors de la fin du téléchargement, décodage et redimensionnement d'une miniature."""

    loaded = Signal(str, str, QImage)  # remote_id, thumb_url, scaled_qimg


class ImageDownloadTask(QRunnable):
    """Tâche asynchrone téléchargeant, décodant et redimensionnant une miniature hors du thread UI."""

    _in_flight: Dict[str, List[Tuple[str, ImageLoadSignals]]] = {}
    _in_flight_lock = threading.Lock()

    def __init__(
        self,
        source: str,
        remote_id: str,
        url: str,
        dest_path: Path,
        signals: ImageLoadSignals,
        target_width: int = 271,
        target_height: int = 145,
    ):
        super().__init__()
        self.source = source
        self.remote_id = remote_id
        self.url = url
        self.dest_path = dest_path
        self.signals = signals
        self.target_width = target_width
        self.target_height = target_height

    @property
    def flight_key(self) -> str:
        """Clé unique identifiant un travail de miniature en cours pour une résolution cible."""
        return f"{self.url}@{self.target_width}x{self.target_height}"

    @classmethod
    def enqueue_or_join(
        cls,
        source: str,
        remote_id: str,
        url: str,
        dest_path: Path,
        signals: ImageLoadSignals,
        target_width: int = 271,
        target_height: int = 145,
    ) -> bool:
        """Planifie la tâche ou abonne les signaux si la même miniature est déjà en cours de traitement.

        Retourne True si une nouvelle tâche a été démarrée, False si fusionnée avec une tâche in-flight.
        """
        key = f"{url}@{target_width}x{target_height}"
        with cls._in_flight_lock:
            if key in cls._in_flight:
                cls._in_flight[key].append((remote_id, signals))
                return False
            cls._in_flight[key] = [(remote_id, signals)]

        task = cls(
            source=source,
            remote_id=remote_id,
            url=url,
            dest_path=dest_path,
            signals=signals,
            target_width=target_width,
            target_height=target_height,
        )
        QThreadPool.globalInstance().start(task)
        return True

    @staticmethod
    def decode_and_scale_qimage(image_path: Path, width: int, height: int) -> Optional[QImage]:
        """Décode un fichier image sur disque et le redimensionne en QImage (thread-safe hors UI)."""
        qimg = QImage(str(image_path))
        if qimg.isNull():
            return None
        return qimg.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    def run(self) -> None:
        """Télécharge si nécessaire, décode et redimensionne la miniature hors du thread UI."""
        key = self.flight_key
        scaled_qimg: Optional[QImage] = None
        try:
            if not (self.dest_path.exists() and self.dest_path.stat().st_size > 100):
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

            if self.dest_path.exists() and self.dest_path.stat().st_size > 100:
                scaled_qimg = self.decode_and_scale_qimage(
                    self.dest_path,
                    self.target_width,
                    self.target_height,
                )
        except Exception as e:
            logger.debug(f"Thumbnail processing failed for {self.url}: {e}")
        finally:
            with self._in_flight_lock:
                subscribers = self._in_flight.pop(key, [(self.remote_id, self.signals)])

            if scaled_qimg is not None and not scaled_qimg.isNull():
                for sub_remote_id, sub_signals in subscribers:
                    try:
                        sub_signals.loaded.emit(sub_remote_id, self.url, scaled_qimg)
                    except RuntimeError:
                        continue


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
        """Vérifie le cache mémoire LRU ou planifie le décodage/téléchargement asynchrone hors UI."""
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

        self._reset_thumbnail_placeholder()
        ImageDownloadTask.enqueue_or_join(
            source=source,
            remote_id=remote_id,
            url=thumb_url,
            dest_path=cache_path,
            signals=self.signals,
            target_width=self.thumb_width,
            target_height=self.thumb_height,
        )

    def _on_image_loaded(self, remote_id: str, thumb_url: str, scaled_qimg: QImage) -> None:
        """Callback UI recevant le QImage déjà décodé et redimensionné par le worker thread."""
        if scaled_qimg.isNull():
            return
        scaled_pix = QPixmap.fromImage(scaled_qimg)
        if thumb_url:
            ImageCache.set_scaled(thumb_url, self.thumb_width, self.thumb_height, scaled_pix)
        if str(self.mod_data.get("remote_id")) == remote_id and self.thumb_label:
            self.thumb_label.setPixmap(scaled_pix)
            self.thumb_label.setText("")
