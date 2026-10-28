from unittest.mock import MagicMock, patch
from src.application.dependencies.requirement_reporter_service import RequirementReporterService


def test_format_author_mention():
    assert RequirementReporterService.format_author_mention("TurboDriver") == "@TurboDriver"
    assert RequirementReporterService.format_author_mention("@TurboDriver") == "@TurboDriver"
    assert RequirementReporterService.format_author_mention("") == "@Author"
    assert RequirementReporterService.format_author_mention("   ") == "@Author"


def test_build_english_subject():
    subj = RequirementReporterService.build_english_subject("Confidence Cascade")
    assert subj == '[Sims 4 Mods Manager] Requirements feedback for "Confidence Cascade"'


def test_build_english_message():
    msg = RequirementReporterService.build_english_message(
        mod_title="Custom Wicked Animations",
        author="KikiSims",
        missing_modules=["WW Core Package", "Nisa Kinky Pack"],
    )
    assert "Hi @KikiSims," in msg
    assert "Custom Wicked Animations" in msg
    assert "Sims 4 Mods Manager" in msg
    assert "- WW Core Package" in msg
    assert "- Nisa Kinky Pack" in msg
    assert "Unresolved / Missing Dependencies" in msg
    assert "Could you please check or clarify the exact file name" in msg
    assert "Thank you" in msg


def test_build_english_message_with_unnecessary_and_mixed():
    # Only unnecessary items
    msg_unnecessary = RequirementReporterService.build_english_message(
        mod_title="Conversation Mod",
        author="ModMaker",
        unnecessary_modules=["No third-party library is required", "Script mods enabled"],
    )
    assert "Hi @ModMaker," in msg_unnecessary
    assert "Notes / Instructions to clean from Requirements" in msg_unnecessary
    assert "- No third-party library is required" in msg_unnecessary
    assert "- Script mods enabled" in msg_unnecessary
    assert "Sims 4 Mods Manager" in msg_unnecessary

    # Mixed missing and unnecessary
    msg_mixed = RequirementReporterService.build_english_message(
        mod_title="Complex Mod",
        author="SimAuthor",
        missing_modules=["Real Missing Library"],
        unnecessary_modules=["Conversation lock is a script only mod"],
    )
    assert "📦 Unresolved / Missing Dependencies" in msg_mixed
    assert "- Real Missing Library" in msg_mixed
    assert "🧹 Notes / Instructions to clean from Requirements" in msg_mixed
    assert "- Conversation lock is a script only mod" in msg_mixed
    assert "Sims 4 Mods Manager" in msg_mixed


def test_check_report_status_not_authenticated():
    with patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=False):
        res = RequirementReporterService.check_report_status(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["can_report"] is False
        assert res["already_reported"] is False
        assert res["is_authenticated"] is False
        assert "non connecté" in res["reason"]


def test_check_report_status_already_commented():
    mock_provider = MagicMock()
    mock_provider.check_user_already_commented.return_value = (True, "12/09/2026 à 14:32")

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider),
    ):
        res = RequirementReporterService.check_report_status(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["can_report"] is False
        assert res["already_reported"] is True
        assert res["reported_at"] == "12/09/2026 à 14:32"
        assert res["is_authenticated"] is True
        mock_provider.check_user_already_commented.assert_called_once()


def test_check_report_status_can_report():
    mock_provider = MagicMock()
    mock_provider.check_user_already_commented.return_value = (False, None)

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider),
    ):
        res = RequirementReporterService.check_report_status(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["can_report"] is True
        assert res["already_reported"] is False
        assert res["reported_at"] is None
        assert res["is_authenticated"] is True


def test_check_report_status_forum_comment_detected():
    """Verifies that check_report_status detects existing forum comments on the mod topic."""
    mock_provider = MagicMock()
    mock_provider.get_creator_info.return_value = (
        "10930102",
        "BlackBoxMods",
        "https://www.loverslab.com/profile/10930102-blackboxmods/",
    )
    mock_provider.check_user_already_commented.return_value = (True, "27/09/2026 à 15:18")

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider),
    ):
        res = RequirementReporterService.check_report_status(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/51444-confidence-cascade/",
            mod_title="Confidence Cascade",
            author="BlackBoxMods",
            missing_modules=["MissingLib"],
        )
        assert res["can_report"] is False
        assert res["already_reported"] is True
        assert res["reported_at"] == "27/09/2026 à 15:18"
        mock_provider.check_user_already_commented.assert_called_once()


def test_submit_report_blocks_when_already_reported():
    mock_provider = MagicMock()
    mock_provider.check_user_already_commented.return_value = (True, "12/09/2026 à 14:32")

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider),
    ):
        res = RequirementReporterService.submit_report(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["success"] is False
        assert res["already_reported"] is True
        assert "déjà été" in res["message"]
        mock_provider.post_mod_comment.assert_not_called()


def test_submit_report_success():
    mock_provider = MagicMock()
    mock_provider.get_creator_info.return_value = (None, None, None)
    mock_provider.check_user_already_sent_pm.return_value = (False, None)
    mock_provider.check_user_already_commented.return_value = (False, None)
    mock_provider.post_mod_comment.return_value = (True, "Message publié avec succès sur le forum LoversLab.")

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider),
    ):
        res = RequirementReporterService.submit_report(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
            send_as_pm=False,
        )
        assert res["success"] is True
        assert res["already_reported"] is True
        assert res["reported_at"] == "à l'instant"
        mock_provider.post_mod_comment.assert_called_once()


def test_submit_report_pm_success():
    mock_provider = MagicMock()
    mock_provider.get_creator_info.return_value = (
        "10930102",
        "BlackBoxMods",
        "https://www.loverslab.com/profile/10930102-blackboxmods/",
    )
    mock_provider.check_user_already_sent_pm.return_value = (False, None)
    mock_provider.check_user_already_commented.return_value = (False, None)
    mock_provider.send_private_message.return_value = (
        True,
        "Message privé envoyé avec succès au créateur sur LoversLab.",
    )

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider),
    ):
        res = RequirementReporterService.submit_report(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/51444-confidence-cascade/",
            mod_title="Confidence Cascade",
            author="BlackBoxMods",
            missing_modules=["MissingLib"],
            send_as_pm=True,
        )
        assert res["success"] is True
        assert res["already_reported"] is True
        mock_provider.send_private_message.assert_called_once()
        args = mock_provider.send_private_message.call_args[0]
        assert args[0] == "10930102"
        assert args[1] == "BlackBoxMods"
        assert "Requirements feedback" in args[2]
