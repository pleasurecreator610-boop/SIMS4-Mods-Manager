import threading
import time
import pytest

from src.application.mods.active_installation_registry import ActiveInstallationRegistry


@pytest.fixture(autouse=True)
def clean_registry():
    ActiveInstallationRegistry.reset()
    yield
    ActiveInstallationRegistry.reset()


def test_registry_singleton_and_basic_registration():
    reg1 = ActiveInstallationRegistry.get_instance()
    reg2 = ActiveInstallationRegistry.get_instance()
    assert reg1 is reg2

    acquired, event = reg1.register_install("loverslab", "12345", "Test Mod")
    assert acquired is True
    assert isinstance(event, threading.Event)
    assert not event.is_set()
    assert reg1.is_active("loverslab", "12345") is True
    assert reg1.is_active("loverslab", "99999") is False


def test_registry_reentrancy_on_same_thread():
    reg = ActiveInstallationRegistry.get_instance()
    acquired1, _ = reg.register_install("loverslab", "12345", "WickedWhims")
    assert acquired1 is True

    # Same thread calling again (cascade dependency) should be allowed without self-deadlock
    acquired2, _ = reg.register_install("loverslab", "12345", "WickedWhims")
    assert acquired2 is True


def test_registry_deduplication_different_thread_denied():
    reg = ActiveInstallationRegistry.get_instance()
    acquired1, event1 = reg.register_install("loverslab", "12345", "WickedWhims")
    assert acquired1 is True

    results = []

    def second_worker():
        acquired2, event2 = reg.register_install("loverslab", "12345", "WickedWhims")
        results.append((acquired2, event2))

    t2 = threading.Thread(target=second_worker)
    t2.start()
    t2.join(timeout=2.0)

    assert len(results) == 1
    acquired2, event2 = results[0]
    assert acquired2 is False
    assert event1 is event2


def test_registry_deduplication_by_title_different_thread():
    reg = ActiveInstallationRegistry.get_instance()
    acquired1, _ = reg.register_install("loverslab", "", "UniqueModName")
    assert acquired1 is True

    results = []

    def second_worker():
        acquired2, _ = reg.register_install("loverslab", "", "uniquemodname")
        results.append(acquired2)

    t2 = threading.Thread(target=second_worker)
    t2.start()
    t2.join(timeout=2.0)

    assert results == [False]


def test_wait_for_active_install_and_complete():
    reg = ActiveInstallationRegistry.get_instance()
    reg.register_install("loverslab", "55555", "Shared Library")

    results = []

    def background_waiter():
        ok, msg = reg.wait_for_active_install("loverslab", "55555", "Shared Library", timeout=5.0)
        results.append((ok, msg))

    thread = threading.Thread(target=background_waiter)
    thread.start()

    time.sleep(0.05)
    assert len(results) == 0  # Still waiting

    # First installer completes successfully
    reg.complete_install("loverslab", "55555", "Shared Library", success=True, message="Installed successfully")

    thread.join(timeout=2.0)
    assert len(results) == 1
    assert results[0] == (True, "Installed successfully")
    assert reg.is_active("loverslab", "55555") is False


def test_wait_for_active_install_timeout_different_thread():
    reg = ActiveInstallationRegistry.get_instance()
    reg.register_install("loverslab", "77777", "Slow Mod")

    results = []

    def waiter():
        ok, msg = reg.wait_for_active_install("loverslab", "77777", "Slow Mod", timeout=0.05)
        results.append((ok, msg))

    t = threading.Thread(target=waiter)
    t.start()
    t.join(timeout=2.0)

    assert len(results) == 1
    ok, msg = results[0]
    assert ok is False
    assert "Timeout" in msg


def test_completed_cache():
    reg = ActiveInstallationRegistry.get_instance()
    reg.register_install("loverslab", "88888", "Cached Mod")
    reg.complete_install("loverslab", "88888", "Cached Mod", success=True, message="Done")

    # Immediate lookup after completion
    ok, msg = reg.wait_for_active_install("loverslab", "88888", "Cached Mod")
    assert ok is True
    assert msg == "Done"


def test_complete_install_cleans_title_even_when_omitted():
    reg = ActiveInstallationRegistry.get_instance()
    reg.register_install("loverslab", "99999", "My Mod With Title")
    assert reg.is_active("loverslab", "99999") is True
    assert reg.is_active("loverslab", "", "My Mod With Title") is True

    # Complete without passing title
    reg.complete_install("loverslab", "99999", title="", success=True, message="Finished")

    # Both key and title should be purged completely
    assert reg.is_active("loverslab", "99999") is False
    assert reg.is_active("loverslab", "", "My Mod With Title") is False
