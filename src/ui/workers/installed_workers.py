"""
Workers d'arrière-plan pour la gestion des mods installés :
- Scan asynchrone du dossier Mods (InstalledScanWorker)
- Récupération asynchrone des mods installés (InstalledFetchWorker)
- Diagnostic asynchrone des conflits DBPF (ConflictsWorker)
"""

from PySide6.QtCore import Signal
from src.utils.logger import logger
from src.utils.thread_utils import BaseWorker


class InstalledScanWorker(BaseWorker):
    """Exécute le scan récursif du dossier Mods sans bloquer la boucle d'événements Qt."""

    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client

    def run(self):
        try:
            self._is_running = True
            if self._is_cancelled:
                return
            res = self.api_client.scan_installed_mods()
            if not self._is_cancelled:
                self.finished_signal.emit(res)
        except Exception as e:
            logger.error(f"Erreur InstalledScanWorker: {e}")
            if not self._is_cancelled:
                self.error_signal.emit(str(e))
        finally:
            self._is_running = False


class InstalledFetchWorker(BaseWorker):
    """Charge la liste des mods installés en tâche de fond pour une UI 100% fluide."""

    data_ready = Signal(list)
    error_signal = Signal(str)

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client

    def run(self):
        try:
            self._is_running = True
            if self._is_cancelled:
                return
            res = self.api_client.get_installed_mods()
            if isinstance(res, dict):
                mods = res.get("items", res.get("mods", []))
            else:
                mods = res or []
            if not self._is_cancelled:
                self.data_ready.emit(mods)
        except Exception as e:
            logger.error(f"Erreur InstalledFetchWorker: {e}")
            if not self._is_cancelled:
                self.error_signal.emit(str(e))
        finally:
            self._is_running = False


class ConflictsWorker(BaseWorker):
    """Exécute l'analyse DBPF des conflits TGI sans figer l'interface."""

    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client

    def run(self):
        try:
            self._is_running = True
            if self._is_cancelled:
                return
            res = self.api_client.get_mod_conflicts()
            if not self._is_cancelled:
                self.finished_signal.emit(res)
        except Exception as e:
            logger.error(f"Erreur ConflictsWorker: {e}")
            if not self._is_cancelled:
                self.error_signal.emit(str(e))
        finally:
            self._is_running = False
