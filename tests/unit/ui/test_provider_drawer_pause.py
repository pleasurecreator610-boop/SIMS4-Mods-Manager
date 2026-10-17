from src.ui.components.provider_drawer.loverslab_card import LoversLabDrawerCard
from src.ui.components.provider_drawer.drawer import ProviderDrawer


def test_loverslab_card_pause_and_running_states(qapp):
    card = LoversLabDrawerCard()

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
