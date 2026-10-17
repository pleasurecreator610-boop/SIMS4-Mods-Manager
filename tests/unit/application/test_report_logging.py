from unittest.mock import patch, MagicMock
from src.providers.loverslab.forum_service import LoversLabForumService
from src.application.dependencies.requirement_reporter_service import RequirementReporterService
from src.ui.workers.report_workers import SubmitReportWorker


def test_forum_service_logs_error_on_unauthenticated():
    with patch("src.providers.loverslab.forum_service.SessionManager.is_member_authenticated", return_value=False):
        with patch("src.providers.loverslab.forum_service.logger.error") as mock_err:
            success, msg = LoversLabForumService.post_mod_comment("https://example.com/mod", "Test message")
            assert not success
            mock_err.assert_called()
            assert any("non authentifié" in str(c) for c in mock_err.call_args_list)


def test_forum_service_logs_error_on_http_failure():
    mock_session = MagicMock()
    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.text = '<html><input name="csrfKey" value="1234567890abcdef1234567890abcdef"></html>'
    mock_session.get.return_value = mock_get

    mock_post = MagicMock()
    mock_post.status_code = 403
    mock_post.text = "Forbidden / Cloudflare"
    mock_session.post.return_value = mock_post

    with patch("src.providers.loverslab.forum_service.SessionManager.is_member_authenticated", return_value=True):
        with patch("src.providers.loverslab.forum_service.SessionManager.get_http_session", return_value=mock_session):
            with patch("src.providers.loverslab.forum_service.logger.error") as mock_err:
                success, msg = LoversLabForumService.post_mod_comment("https://example.com/mod", "Test message")
                assert not success
                mock_err.assert_called()
                assert any("403" in str(c) for c in mock_err.call_args_list)


def test_requirement_reporter_service_logs_error_on_failure():
    mock_provider = MagicMock()
    mock_provider.post_mod_comment.return_value = (False, "HTTP 500 error")

    with patch(
        "src.application.dependencies.requirement_reporter_service.ProviderRegistry.get_provider",
        return_value=mock_provider,
    ):
        with patch.object(
            RequirementReporterService,
            "check_report_status",
            return_value={"is_authenticated": True, "already_reported": False, "formatted_message": "Hello"},
        ):
            with patch("src.application.dependencies.requirement_reporter_service.logger.error") as mock_err:
                res = RequirementReporterService.submit_report(
                    source="loverslab",
                    page_url="https://example.com/mod",
                    mod_title="TestMod",
                    author="Author",
                    missing_modules=["ModuleA"],
                )
                assert not res["success"]
                mock_err.assert_called()
                assert any("Échec de l'envoi" in str(c) for c in mock_err.call_args_list)


def test_submit_report_worker_logs_error_on_failure():
    mock_client = MagicMock()
    mock_client.report_missing_requirements.return_value = {
        "success": False,
        "message": "Erreur HTTP 403",
    }

    worker = SubmitReportWorker(payload={"title": "TestMod", "page_url": "https://example.com"})
    with patch("src.ui.workers.report_workers.get_api_client", return_value=mock_client):
        with patch("src.ui.workers.report_workers.logger.error") as mock_err:
            worker.run()
            mock_err.assert_called()
            assert any("Échec envoi rapport" in str(c) for c in mock_err.call_args_list)
