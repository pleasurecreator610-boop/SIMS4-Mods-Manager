"""
GameLauncher: Locates Sims 4 game executable via common paths, EA app, Origin, Steam,
and Windows registry, and handles process execution.
"""

import os

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]
import subprocess
from pathlib import Path
from typing import Optional

from src.core.config import AppConfig
from src.utils.logger import logger


class GameLauncher:
    """Detects game executable and handles process launching."""

    _cached_game_exe: Optional[Path] = None

    @classmethod
    def clear_cache(cls) -> None:
        """Exécute l'opération clear cache.

        Returns:
            Résultat de l'opération clear_cache.
        """
        cls._cached_game_exe = None

    @classmethod
    def detect_game_executable(cls, custom_exe: Optional[str] = None) -> Optional[Path]:
        """Locates TS4_x64.exe or TS4_DX9_x64.exe."""
        if custom_exe and Path(custom_exe).exists():
            return Path(custom_exe)

        if cls._cached_game_exe and cls._cached_game_exe.exists():
            return cls._cached_game_exe

        config = AppConfig.load()
        if config.custom_game_exe:
            custom_p = Path(config.custom_game_exe)
            if custom_p.exists() and custom_p.is_file():
                cls._cached_game_exe = custom_p
                return custom_p

        if config.cached_game_exe:
            cached_exe = Path(config.cached_game_exe)
            if cached_exe.exists() and cached_exe.is_file():
                cls._cached_game_exe = cached_exe
                return cached_exe

        exe = cls._do_detect_game_executable()
        if exe:
            cls._cached_game_exe = exe
            config.cached_game_exe = str(exe)
            config.save()
        return exe

    @classmethod
    def _do_detect_game_executable(cls) -> Optional[Path]:
        common_paths = [
            r"D:\Origin\The Sims 4\Game\Bin\TS4_x64.exe",
            r"D:\Origin\The Sims 4\Game\Bin\TS4_DX9_x64.exe",
            r"C:\Program Files\EA Games\The Sims 4\Game\Bin\TS4_x64.exe",
            r"C:\Program Files (x86)\Origin Games\The Sims 4\Game\Bin\TS4_x64.exe",
            r"C:\Program Files (x86)\Steam\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe",
            r"D:\SteamLibrary\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe",
            r"E:\SteamLibrary\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe",
            r"D:\EA Games\The Sims 4\Game\Bin\TS4_x64.exe",
            r"C:\Origin Games\The Sims 4\Game\Bin\TS4_x64.exe",
        ]

        for p_str in common_paths:
            p = Path(p_str)
            if p.exists():
                logger.info(f"Found Sims 4 executable at common path: {p}")
                return p

        if winreg is not None:
            for reg_root, reg_key in [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Maxis\The Sims 4"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Maxis\The Sims 4"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Electronic Arts\EA Games\The Sims 4"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Origin Games\1011164"),
            ]:
                try:
                    with winreg.OpenKey(reg_root, reg_key) as key:
                        for val_name in ["Install Dir", "path", "InstallDir"]:
                            try:
                                val, _ = winreg.QueryValueEx(key, val_name)
                                install_dir = Path(val)
                                exe_candidates = [
                                    install_dir / "Game" / "Bin" / "TS4_x64.exe",
                                    install_dir / "Game" / "Bin" / "TS4_DX9_x64.exe",
                                    install_dir / "Game" / "Bin" / "TS4_Launcher_x64.exe",
                                    install_dir / "TS4_x64.exe",
                                ]
                                for exe in exe_candidates:
                                    if exe.exists():
                                        logger.info(f"Found Sims 4 executable via registry: {exe}")
                                        return exe
                            except Exception:
                                continue
                except Exception:
                    pass

        return None

    @classmethod
    def open_system_uri(cls, uri: str) -> bool:
        """Opens a custom URI scheme across Windows, Linux, and macOS safely."""
        try:
            startfile_fn = getattr(os, "startfile", None)
            if callable(startfile_fn):
                startfile_fn(uri)
                return True
            import sys

            if sys.platform == "darwin":
                subprocess.Popen(["open", uri])
                return True
            else:
                subprocess.Popen(["xdg-open", uri])
                return True
        except Exception as e:
            logger.debug(f"Impossible d'ouvrir l'URI système '{uri}': {e}")
            return False

    @classmethod
    def launch_game(cls, exe_path: Optional[Path] = None) -> bool:
        """Launches the Sims 4 game process."""
        if not exe_path:
            exe_path = cls.detect_game_executable()

        if exe_path and exe_path.exists():
            try:
                logger.info(f"Launching Sims 4 from: {exe_path}")
                subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
                return True
            except Exception as e:
                logger.error(f"Failed to launch game executable: {e}")
                return False

        logger.info("Tentative de lancement via le protocole EA App / Origin...")
        if cls.open_system_uri("origin2://game/launch?offerIds=1011164"):
            return True

        logger.info("Tentative de lancement via le protocole Steam (steam://rungameid/1222670)...")
        if cls.open_system_uri("steam://rungameid/1222670"):
            return True

        return False

    @classmethod
    def is_game_running(cls) -> bool:
        """Vérifie si un processus The Sims 4 est actuellement en cours d'exécution via API native ultra-rapide."""
        target_exes = {"ts4_x64.exe", "ts4_dx9_x64.exe", "ts4.exe", "ts4_launcher_x64.exe"}
        try:
            if os.name == "nt":
                # Optimisation Windows : inspection native par snapshot Win32 (< 5ms au lieu de 480ms avec tasklist)
                try:
                    import ctypes
                    from ctypes import wintypes

                    class PROCESSENTRY32(ctypes.Structure):
                        _fields_ = [
                            ("dwSize", wintypes.DWORD),
                            ("cntUsage", wintypes.DWORD),
                            ("th32ProcessID", wintypes.DWORD),
                            ("th32DefaultHeapID", ctypes.c_size_t),
                            ("th32ModuleID", wintypes.DWORD),
                            ("cntThreads", wintypes.DWORD),
                            ("th32ParentProcessID", wintypes.DWORD),
                            ("pcPriClassBase", ctypes.c_long),
                            ("dwFlags", wintypes.DWORD),
                            ("szExeFile", ctypes.c_char * 260),
                        ]

                    kernel32 = ctypes.windll.kernel32
                    h_snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
                    if h_snap not in (-1, 0):
                        try:
                            entry = PROCESSENTRY32()
                            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
                            success = kernel32.Process32First(h_snap, ctypes.byref(entry))
                            while success:
                                exe_name = entry.szExeFile.decode("utf-8", errors="ignore").lower()
                                if exe_name in target_exes:
                                    return True
                                success = kernel32.Process32Next(h_snap, ctypes.byref(entry))
                        finally:
                            kernel32.CloseHandle(h_snap)
                        return False
                except Exception:
                    pass

                # Repli de secours subprocess si ctypes indisponible
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                out = subprocess.check_output(
                    ["tasklist", "/NH", "/FO", "CSV"],
                    creationflags=flags,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                ).lower()
                return any(exe in out for exe in target_exes)
            else:
                out = subprocess.check_output(["ps", "-A"], text=True, errors="ignore").lower()
                return any(exe in out for exe in target_exes)
        except Exception as e:
            logger.debug(f"Vérification du processus Sims 4 échouée: {e}")
            return False
