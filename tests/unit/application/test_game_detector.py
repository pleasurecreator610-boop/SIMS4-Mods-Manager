from src.application.game.game_service import GameDetector, LOCALIZED_SIMS4_FOLDERS
from src.utils.resource_cfg import ensure_resource_cfg


def test_localized_folder_names():
    assert "Les Sims 4" in LOCALIZED_SIMS4_FOLDERS
    assert "The Sims 4" in LOCALIZED_SIMS4_FOLDERS
    assert "Die Sims 4" in LOCALIZED_SIMS4_FOLDERS
    assert "Los Sims 4" in LOCALIZED_SIMS4_FOLDERS


def test_resource_cfg_creation(tmp_path):
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()

    ok = ensure_resource_cfg(mods_dir)
    assert ok is True

    cfg_file = mods_dir / "Resource.cfg"
    assert cfg_file.exists()
    content = cfg_file.read_text(encoding="utf-8")
    assert "*/*/*/*.package" in content


def test_detect_sims4_user_dir_custom(tmp_path):
    custom_dir = tmp_path / "CustomSims"
    custom_dir.mkdir()

    detected = GameDetector.detect_sims4_user_dir(str(custom_dir))
    assert detected == custom_dir


def test_detect_mods_dir_custom(tmp_path):
    custom_mods = tmp_path / "CustomMods"
    custom_mods.mkdir()

    detected = GameDetector.detect_mods_dir(str(custom_mods))
    assert detected == custom_mods
    assert (custom_mods / "Resource.cfg").exists()


def test_game_detector_cache():
    GameDetector.clear_cache()
    # Cache should start None
    assert GameDetector._cached_mods_dir is None
    assert GameDetector._cached_game_exe is None


def test_non_breaking_space_sims4_detection(tmp_path, monkeypatch):
    GameDetector.clear_cache()
    # Simulate Documents/Electronic Arts/Les\xa0Sims\xa04
    docs_dir = tmp_path / "Documents"
    ea_dir = docs_dir / "Electronic Arts"
    sims_french_dir = ea_dir / "Les\xa0Sims\xa04"
    sims_french_dir.mkdir(parents=True)

    monkeypatch.setattr(GameDetector, "get_windows_documents_dirs", staticmethod(lambda: [docs_dir]))

    detected = GameDetector.detect_sims4_user_dir()
    assert detected == sims_french_dir

    mods = GameDetector.detect_mods_dir()
    assert mods == sims_french_dir / "Mods"
    assert (mods / "Resource.cfg").exists()


def test_game_launcher_ea_app_and_steam_fallbacks(monkeypatch):
    from src.application.game.game_launcher import GameLauncher

    called_uris = []
    monkeypatch.setattr(GameLauncher, "detect_game_executable", classmethod(lambda cls, custom_exe=None: None))
    monkeypatch.setattr(
        GameLauncher, "open_system_uri", classmethod(lambda cls, uri: (called_uris.append(uri) or True))
    )

    ok = GameLauncher.launch_game()
    assert ok is True
    # Premier repli : EA App / Origin
    assert len(called_uris) >= 1
    assert "origin2://game/launch" in called_uris[0]


def test_game_launcher_steam_fallback_when_ea_fails(monkeypatch):
    from src.application.game.game_launcher import GameLauncher

    called_uris = []

    def mock_open_uri(uri):
        called_uris.append(uri)
        if "origin2://" in uri:
            return False
        return True

    monkeypatch.setattr(GameLauncher, "detect_game_executable", classmethod(lambda cls, custom_exe=None: None))
    monkeypatch.setattr(GameLauncher, "open_system_uri", classmethod(lambda cls, uri: mock_open_uri(uri)))

    ok = GameLauncher.launch_game()
    assert ok is True
    assert len(called_uris) == 2
    assert "origin2://" in called_uris[0]
    assert "steam://rungameid/1222670" in called_uris[1]


def test_detect_mods_dir_honors_app_config_custom_mods_dir(tmp_path, monkeypatch):
    GameDetector.clear_cache()
    from src.core.config import AppConfig

    custom_mods = tmp_path / "MySpecialModsFolder"
    custom_mods.mkdir()

    cfg = AppConfig(custom_mods_dir=str(custom_mods))
    monkeypatch.setattr(AppConfig, "load", classmethod(lambda cls: cfg))

    # Calling detect_mods_dir() with no arguments must pick up custom_mods_dir
    res = GameDetector.detect_mods_dir()
    assert res == custom_mods
    assert (custom_mods / "Resource.cfg").exists()
