"""Tests unitaires pour AppContainer."""

import pytest
from src.core.container import AppContainer, get_container


def test_app_container_singleton():
    AppContainer.reset()
    c1 = get_container()
    c2 = get_container()
    assert c1 is c2


def test_app_container_resolve_defaults():
    AppContainer.reset()
    container = get_container()

    db = container.get_database_manager()
    assert db is not None

    extractor = container.get_archive_extractor()
    assert extractor is not None

    downloader = container.get_file_downloader()
    assert downloader is not None


def test_app_container_override():
    AppContainer.reset()
    container = get_container()

    class MockService:
        pass

    mock_inst = MockService()
    container.register_singleton("custom_service", mock_inst)

    assert container.resolve("custom_service") is mock_inst


def test_app_container_unknown_key():
    AppContainer.reset()
    container = get_container()

    with pytest.raises(KeyError):
        container.resolve("non_existent_key")
