from src.ui.components.provider_drawer.provider_scraper_card import ProviderScraperDrawerCard
from src.ui.components.provider_drawer.drawer import ProviderDrawer


def test_loverslab_card_pause_and_running_states(qapp):
    card = ProviderScraperDrawerCard()

    # 1. State: Running
    status_running = {
        "is_running": True,
        "is_paused": False,
        "progress_percent": 45,
        "pages_completed": 9,
        "total_pages": 20,
        "current_category": "Clothing",
        "has_error": False,
        "total_scraped": 225,
        "categories_progress": [],
    }
    card.update_status(status_running)
    assert not card._current_is_paused
    # Pause button should offer to pause
    assert any(w in card.btn_pause_resume.text().lower() for w in ["pause", "mettre en pause"])
    # Resync button should show in-progress without malformed raw keys
    assert "[" not in card.btn_resync.text()
    assert "]" not in card.btn_resync.text()
    assert any(w in card.btn_resync.text().lower() for w in ["cours", "progress", "curso"])

    # 2. State: Paused
    status_paused = {
        "is_running": True,
        "is_paused": True,
        "progress_percent": 45,
        "pages_completed": 9,
        "total_pages": 20,
        "current_category": "Clothing",
        "has_error": False,
        "total_scraped": 225,
        "categories_progress": [],
    }
    card.update_status(status_paused)
    assert card._current_is_paused
    # Pause button should toggle to resume
    assert any(w in card.btn_pause_resume.text().lower() for w in ["reprendre", "resume", "reanudar"])
    # Resync button should show paused state without malformed keys
    assert "[" not in card.btn_resync.text()
    assert "]" not in card.btn_resync.text()
    assert any(w in card.btn_resync.text().lower() for w in ["pause", "paused", "pausa"])


def test_provider_drawer_pause_integration(qapp):
    drawer = ProviderDrawer()
    status_paused = {
        "is_running": True,
        "is_paused": True,
        "progress_percent": 30,
        "pages_completed": 6,
        "total_pages": 20,
        "current_category": "Objects",
        "has_error": False,
        "total_scraped": 150,
        "categories_progress": [],
    }
    drawer.update_sync_status(status_paused)
    assert drawer.ll_card._current_is_paused
    assert any(w in drawer.ll_card.btn_pause_resume.text().lower() for w in ["reprendre", "resume", "reanudar"])


def test_provider_drawer_all_providers_present_and_visible(qapp):
    """Verifies that ProviderDrawer includes all 9 platforms with cards and edge pills."""
    drawer = ProviderDrawer()

    # 1. Edge Pills
    expected_pills = [
        drawer.tab_curseforge_pill,
        drawer.tab_tsr_pill,
        drawer.tab_modthesims_pill,
        drawer.tab_simsfinds_pill,
        drawer.tab_nexusmods_pill,
        drawer.tab_mmccworld_pill,
        drawer.tab_patreon_pill,
        drawer.tab_loverslab_pill,
        drawer.tab_nsfwmods_pill,
    ]
    for pill in expected_pills:
        assert pill is not None
        assert pill.text() != ""

    # 2. Scraper Cards
    expected_cards = [
        drawer.cf_card,
        drawer.tsr_card,
        drawer.mts_card,
        drawer.sf_card,
        drawer.nexus_card,
        drawer.mmccw_card,
        drawer.ll_card,
        drawer.nm_card,
    ]
    for card in expected_cards:
        assert card in drawer.scraper_cards
        assert len(card._subcategories_meta) > 0
        assert len(card.subcat_widgets) > 0

    assert drawer.patreon_card is not None

    # 3. Adult Content Filtering
    drawer.set_adult_content_enabled(False)
    assert drawer.ll_card.isHidden() is True
    assert drawer.nm_card.isHidden() is True
    assert drawer.tab_loverslab_pill.isHidden() is True
    assert drawer.tab_nsfwmods_pill.isHidden() is True

    # Safe cards & pills remain visible
    assert drawer.cf_card.isHidden() is False
    assert drawer.tsr_card.isHidden() is False
    assert drawer.mts_card.isHidden() is False
    assert drawer.sf_card.isHidden() is False
    assert drawer.nexus_card.isHidden() is False
    assert drawer.mmccw_card.isHidden() is False
    assert drawer.tab_curseforge_pill.isHidden() is False
    assert drawer.tab_tsr_pill.isHidden() is False
    assert drawer.tab_modthesims_pill.isHidden() is False
    assert drawer.tab_simsfinds_pill.isHidden() is False
    assert drawer.tab_nexusmods_pill.isHidden() is False
    assert drawer.tab_mmccworld_pill.isHidden() is False

    # 4. Multi-provider Progress Update
    multi_status = {
        "is_running": True,
        "is_paused": False,
        "progress_percent": 50,
        "pages_completed": 10,
        "total_pages": 20,
        "current_category": "Clothing",
        "has_error": False,
        "total_scraped": 200,
        "providers_status": {
            "curseforge": "RUNNING",
            "thesimsresource": "RUNNING",
            "modthesims": "RUNNING",
            "simsfinds": "RUNNING",
            "nexusmods": "RUNNING",
            "mmccworld": "RUNNING",
            "loverslab": "RUNNING",
            "nsfwmods": "RUNNING",
        },
        "categories_progress": [
            {
                "id": "mts_game_mods",
                "name": "Game Mods (MTS)",
                "pages_completed": 3,
                "total_pages": 5,
                "mods_count": 45,
                "status": "IN_PROGRESS",
            },
            {
                "id": "sfinds_clothing",
                "name": "Clothing (SimsFinds)",
                "pages_completed": 2,
                "total_pages": 4,
                "mods_count": 30,
                "status": "IN_PROGRESS",
            },
            {
                "id": "nexus_gameplay",
                "name": "Gameplay (Nexus)",
                "pages_completed": 1,
                "total_pages": 3,
                "mods_count": 15,
                "status": "IN_PROGRESS",
            },
            {
                "id": "mmccw_clothing",
                "name": "Clothing (MMCCW)",
                "pages_completed": 2,
                "total_pages": 4,
                "mods_count": 28,
                "status": "IN_PROGRESS",
            },
        ],
    }
    drawer.update_sync_status(multi_status)

    assert drawer.mts_card.last_computed_state == "RUNNING"
    assert drawer.sf_card.last_computed_state == "RUNNING"
    assert drawer.nexus_card.last_computed_state == "RUNNING"
    assert drawer.mmccw_card.last_computed_state == "RUNNING"

    # Verify edge pills reflect running state
    assert "ModTheSims" in drawer.tab_modthesims_pill.text()
    assert "SimsFinds" in drawer.tab_simsfinds_pill.text()
    assert "NexusMods" in drawer.tab_nexusmods_pill.text()
    assert "MMCCWorld" in drawer.tab_mmccworld_pill.text()
