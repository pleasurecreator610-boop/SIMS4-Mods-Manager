"""
Unit tests for:
1. Requirement vs Comment classification (MOD vs COMMENT_NOISE) and user overrides (MOD <-> COMMENT)
   on the new platforms.
2. Creator reporting & comment management (RequirementReporterService) on supported new platforms
   (sims4studio, f95zone, gamebanana, itchio, synthira) after prompting the user to authenticate
   when not logged in, followed by live duplicate checks, posting, and comment deletion once authenticated.
"""

from unittest.mock import MagicMock

from bs4 import BeautifulSoup
import pytest

from src.application.dependencies.dependency_resolver import resolve_mod_dependencies
from src.application.dependencies.requirement_reporter_service import RequirementReporterService
from src.core.session_manager import SessionManager
from src.infrastructure.database import CatalogMod, DatabaseManager, InstalledMod
from src.providers.common.portal_base import extract_portal_requirements
from src.providers.registry import ProviderRegistry

COMMENT_CAPABLE_NEW_PLATFORMS = [
    ("sims4studio", "https://sims4studio.com/thread/13058/pose-player"),
    ("f95zone", "https://f95zone.to/threads/sims-4-mod-pack.182000/"),
    ("gamebanana", "https://gamebanana.com/mods/501234"),
    ("itchio", "https://creator.itch.io/sims4-fantasy-mod"),
    ("synthira", "https://synthira.ru/load/12-1-0-777"),
]


def test_mod_vs_comment_classification_and_manual_toggle_on_new_platforms():
    """
    Tests that conversational notes extracted from new platform descriptions are classified as
    COMMENT_NOISE while real mod prerequisites are extracted as MODs, and that the user can
    manually reclassify any item between MOD and COMMENT via requirements_overrides.
    """
    sample_html = """
    <div class="entry-content">
        <p>Requirements:
        Script Mods Enabled in Game Options
        Andrew's Studio Pose Player
        Custom Mesh Pack by SixamCC</p>
    </div>
    """
    soup = BeautifulSoup(sample_html, "html.parser")
    _req_text, req_status, extracted_deps = extract_portal_requirements(
        soup, base_url="https://sims4studio.com", provider_name="sims4studio"
    )
    assert req_status in ("RESOLVED", "FOUND")
    deps_map = {d["title"]: d for d in extracted_deps}
    assert "Andrew's Pose Player" in deps_map
    assert "Custom Mesh Pack by SixamCC" in deps_map
    assert deps_map["Script Mods Enabled in Game Options"]["status"] == "COMMENT_NOISE"

    db = DatabaseManager.get_instance()
    with db.get_session() as session:
        session.query(CatalogMod).delete()
        session.query(InstalledMod).delete()
        session.commit()

        raw_deps = [
            {
                "source": "sims4studio",
                "remote_id": "",
                "title": "Andrew's Studio Pose Player",
                "url": "",
            },
            {
                "source": "sims4studio",
                "remote_id": "",
                "title": "Mystery Custom Prop Accessory By UnknownCreator",
                "url": "",
            },
        ]

        resolved = resolve_mod_dependencies(
            raw_deps,
            session,
            installed_by_remote={},
            installed_by_title={},
            is_syncing=False,
        )
        deps_by_title = {d.title: d for d in resolved}

        # 1. Andrew's Pose Player is intercepted as official sims4studio framework
        assert deps_by_title["Andrew's Pose Player"].source == "sims4studio"
        assert deps_by_title["Andrew's Pose Player"].status == "DETECTED_NOT_INSTALLED"

        # 2. Unknown missing mod is NOT_DETECTED_FINISHED, then user reclassifies it as COMMENT, then back to MOD
        assert deps_by_title["Mystery Custom Prop Accessory By UnknownCreator"].status == "NOT_DETECTED_FINISHED"

        resolved_after_comment = resolve_mod_dependencies(
            raw_deps,
            session,
            installed_by_remote={},
            installed_by_title={},
            is_syncing=False,
            requirements_overrides={"Mystery Custom Prop Accessory By UnknownCreator": "COMMENT"},
        )
        deps_after_comment = {d.title: d for d in resolved_after_comment}
        assert deps_after_comment["Mystery Custom Prop Accessory By UnknownCreator"].status == "COMMENT_NOISE"

        # Toggle back to MOD
        resolved_after_mod = resolve_mod_dependencies(
            raw_deps,
            session,
            installed_by_remote={},
            installed_by_title={},
            is_syncing=False,
            requirements_overrides={"Mystery Custom Prop Accessory By UnknownCreator": "MOD"},
        )
        deps_after_mod = {d.title: d for d in resolved_after_mod}
        assert deps_after_mod["Mystery Custom Prop Accessory By UnknownCreator"].status == "NOT_DETECTED_FINISHED"


@pytest.mark.parametrize("source,mod_url", COMMENT_CAPABLE_NEW_PLATFORMS)
def test_creator_reporting_requires_auth_then_posts_and_deletes_on_new_platforms(monkeypatch, source, mod_url):
    """
    Verifies the complete creator outreach / comment workflow on new platforms supporting accounts:
    1. When the user is NOT authenticated, SessionManager.is_member_authenticated(source) is False,
       check_report_status returns is_authenticated=False & can_report=False, and submit_report
       refuses to post while prompting the user to log in via the 'Comptes' tab.
    2. Once the user authenticates via SessionManager.save_session, check_report_status builds a valid
       compose_pm_url, submit_report posts the standardized English report (or PM), and
       delete_report deletes the comment.
    """
    ProviderRegistry.discover_plugins()
    SessionManager.clear_session(source)
    assert SessionManager.is_member_authenticated(source) is False

    # 1. Check status and attempt to submit while unauthenticated -> blocked with login prompt
    status_unauth = RequirementReporterService.check_report_status(
        source=source,
        page_url=mod_url,
        mod_title="Test Mod",
        author="CreatorX",
        missing_modules=["Mystery Prop"],
    )
    assert status_unauth["is_authenticated"] is False
    assert status_unauth["can_report"] is False

    res_unauth = RequirementReporterService.submit_report(
        source=source,
        page_url=mod_url,
        mod_title="Test Mod",
        author="CreatorX",
        missing_modules=["Mystery Prop"],
    )
    assert res_unauth["success"] is False
    assert "connecter" in res_unauth["message"].lower()

    # 2. Simulate user authenticating after prompt
    SessionManager.save_session(
        provider_name=source,
        cookies={"session_id": "valid_member_token_123", "xf_user": "999"},
        user_display_name="SimsPlayer42",
        is_authenticated=True,
    )
    assert SessionManager.is_member_authenticated(source) is True

    # 3. Mock live HTTP session for checking, posting & deleting comments on the platform
    mock_http = MagicMock()
    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.url = mod_url
    get_resp.text = """
    <html><body>
        <span class="author"><a href="/user/creatorx">CreatorX</a></span>
        <div class="comments"><div class="comment">Great mod!</div></div>
    </body></html>
    """
    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.url = f"{mod_url}#comment-8888"
    post_resp.text = '<html><body><div id="comment-8888">Posted successfully</div></body></html>'

    mock_http.get.return_value = get_resp
    mock_http.post.return_value = post_resp
    monkeypatch.setattr("src.core.session_manager.SessionManager.get_http_session", lambda *_a, **_k: mock_http)

    status_auth = RequirementReporterService.check_report_status(
        source=source,
        page_url=mod_url,
        mod_title="Test Mod",
        author="CreatorX",
        missing_modules=["Mystery Prop"],
    )
    assert status_auth["is_authenticated"] is True
    assert status_auth["can_report"] is True
    assert status_auth["compose_pm_url"] is not None
    assert status_auth["compose_pm_url"].startswith("http")
    assert "Mystery Prop" in status_auth["formatted_message"]

    # Submit public forum comment
    res_post = RequirementReporterService.submit_report(
        source=source,
        page_url=mod_url,
        mod_title="Test Mod",
        author="CreatorX",
        missing_modules=["Mystery Prop"],
        send_as_pm=False,
    )
    assert res_post["success"] is True

    # Submit direct private message (PM) to creator
    res_pm = RequirementReporterService.submit_report(
        source=source,
        page_url=mod_url,
        mod_title="Test Mod",
        author="CreatorX",
        missing_modules=["Mystery Prop"],
        send_as_pm=True,
    )
    assert res_pm["success"] is True

    # 4. Delete the reported comment
    res_del = RequirementReporterService.delete_report(
        source=source,
        page_url=mod_url,
        mod_title="Test Mod",
        missing_modules=["Mystery Prop"],
    )
    assert res_del["success"] is True
    SessionManager.clear_session(source)
