from unittest.mock import MagicMock, patch
from src.providers.loverslab.scraper import LoversLabProvider


def test_loverslab_check_user_already_commented_found():
    provider = LoversLabProvider()

    mock_html = """
    <html>
        <body>
            <div class="cFileComments">
                <article class="ipsComment" data-memberid="999888">
                    <a href="https://www.loverslab.com/profile/999888-myuser/">MyUser</a>
                    <time datetime="2026-09-12T14:32:00Z" title="12/09/2026 14:32">September 12</time>
                    <div data-role="commentContent" class="ipsType_richText">
                        <p>Hi @Author, in the Requirements section for this mod, the module WW Core Package was not found.</p>
                    </div>
                </article>
            </div>
        </body>
    </html>
    """

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html
    mock_session.get.return_value = mock_resp

    mock_acc = MagicMock()
    mock_acc.user_display_name = "MyUser"
    mock_acc.get_cookies_dict.return_value = {"ips4_member_id": "999888"}

    with (
        patch("src.core.session_manager.SessionManager.get_saved_session", return_value=mock_acc),
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session),
    ):
        found, date_str = provider.check_user_already_commented(
            page_url="https://www.loverslab.com/files/file/3169-test/",
            required_keywords=["WW Core Package"],
        )

        assert found is True
        assert date_str is not None
        assert "12/09/2026" in date_str


def test_loverslab_check_user_already_commented_other_user():
    provider = LoversLabProvider()

    mock_html = """
    <html>
        <body>
            <div class="cFileComments">
                <article class="ipsComment" data-memberid="111222">
                    <a href="https://www.loverslab.com/profile/111222-otheruser/">OtherUser</a>
                    <time datetime="2026-09-12T14:32:00Z" title="12/09/2026 14:32">September 12</time>
                    <div data-role="commentContent" class="ipsType_richText">
                        <p>Hi @Author, requirements WW Core Package not found.</p>
                    </div>
                </article>
            </div>
        </body>
    </html>
    """

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html
    mock_session.get.return_value = mock_resp

    mock_acc = MagicMock()
    mock_acc.user_display_name = "MyUser"
    mock_acc.get_cookies_dict.return_value = {"ips4_member_id": "999888"}

    with (
        patch("src.core.session_manager.SessionManager.get_saved_session", return_value=mock_acc),
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session),
    ):
        found, date_str = provider.check_user_already_commented(
            page_url="https://www.loverslab.com/files/file/3169-test/",
            required_keywords=["WW Core Package"],
        )

        assert found is False
        assert date_str is None


def test_loverslab_post_mod_comment_success():
    provider = LoversLabProvider()

    mock_page_html = """
    <html>
        <body>
            <form action="https://www.loverslab.com/files/file/3169-test/?do=addComment" method="post">
                <input type="hidden" name="csrfKey" value="a1b2c3d4e5f60718293a4b5c6d7e8f90">
            </form>
        </body>
    </html>
    """

    mock_session = MagicMock()
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.text = mock_page_html

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = "<html><body><div>Comment added</div></body></html>"

    mock_session.get.return_value = mock_get_resp
    mock_session.post.return_value = mock_post_resp

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session),
    ):
        success, msg = provider.post_mod_comment(
            page_url="https://www.loverslab.com/files/file/3169-test/",
            message="Hi @Author, please check requirements.",
        )

        assert success is True
        assert "succès" in msg.lower()
        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs["data"]["csrfKey"] == "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        assert "Hi @Author" in call_kwargs["data"]["comment_value"]


def test_loverslab_post_mod_comment_via_support_topic():
    provider = LoversLabProvider()

    # File page with no form, only 'Get Support' button
    file_html = """
    <html>
        <body>
            <div class="ipsItemControls">
                <a href="https://www.loverslab.com/topic/270782-confidence-cascade/" class="ipsButton">Get Support</a>
            </div>
        </body>
    </html>
    """

    # Topic page with dynamic IPS form
    topic_html = """
    <html>
        <body>
            <form class="ipsForm ipsForm_vertical" action="https://www.loverslab.com/topic/270782-confidence-cascade/" method="post">
                <input type="hidden" name="csrfKey" value="deadbeef1234567890abcdef12345678">
                <input type="hidden" name="commentform_270782_submitted" value="1">
                <input type="hidden" name="_contentReply" value="1">
                <textarea name="topic_comment_270782_noscript"></textarea>
                <textarea data-role="contentEditor" name="topic_comment_270782"></textarea>
                <button type="submit">Submit Reply</button>
            </form>
        </body>
    </html>
    """

    mock_session = MagicMock()

    def get_side_effect(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "files/file" in url:
            resp.text = file_html
        else:
            resp.text = topic_html
        return resp

    mock_session.get.side_effect = get_side_effect

    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.text = "<html><body><div>Reply posted</div></body></html>"
    mock_session.post.return_value = post_resp

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session),
    ):
        success, msg = provider.post_mod_comment(
            page_url="https://www.loverslab.com/files/file/51444-confidence-cascade/",
            message="Hi @BlackBoxMods, missing dependencies detected.",
        )

        assert success is True
        assert "succès" in msg.lower()
        mock_session.post.assert_called_once()
        target_url = mock_session.post.call_args[0][0]
        assert target_url == "https://www.loverslab.com/topic/270782-confidence-cascade/"
        post_data = mock_session.post.call_args[1]["data"]
        assert post_data["csrfKey"] == "deadbeef1234567890abcdef12345678"
        assert post_data["commentform_270782_submitted"] == "1"
        assert post_data["_contentReply"] == "1"
        assert post_data["topic_comment_270782_noscript"] == "Hi @BlackBoxMods, missing dependencies detected."
        assert "<p>Hi @BlackBoxMods, missing dependencies detected.</p>" in post_data["topic_comment_270782"]


def test_loverslab_extract_creator_info():
    from bs4 import BeautifulSoup
    from src.providers.loverslab.forum_service import LoversLabForumService

    html = """
    <html>
        <body>
            <div class="ipsPhotoPanel">
                <a href="https://www.loverslab.com/profile/10930102-blackboxmods/">BlackBoxMods</a>
            </div>
            <a href="https://www.loverslab.com/profile/10930102-blackboxmods/content/?type=downloads_file">Find their other files</a>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    cid, cname, curl = LoversLabForumService.extract_creator_info(soup, "https://www.loverslab.com/files/file/51444/")

    assert cid == "10930102"
    assert cname == "BlackBoxMods"
    assert "https://www.loverslab.com/profile/10930102-blackboxmods/" in curl


def test_loverslab_send_private_message_success():
    provider = LoversLabProvider()

    compose_html = """
    <html>
        <body>
            <form class="ipsForm" action="https://www.loverslab.com/messenger/compose/?to=10930102" method="post">
                <input type="hidden" name="form_submitted" value="1">
                <input type="hidden" name="csrfKey" value="abc1234567890defabc1234567890def">
                <input type="hidden" name="MAX_FILE_SIZE" value="103809024">
                <textarea name="messenger_to">BlackBoxMods</textarea>
                <input type="text" name="messenger_title" value="">
                <textarea name="messenger_content_noscript"></textarea>
                <textarea name="messenger_content"></textarea>
            </form>
        </body>
    </html>
    """

    mock_session = MagicMock()
    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.text = compose_html
    mock_session.get.return_value = mock_get

    mock_post = MagicMock()
    mock_post.status_code = 200
    mock_post.text = "<html><body><div>Message sent</div></body></html>"
    mock_session.post.return_value = mock_post

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session),
    ):
        success, msg = provider.send_private_message(
            creator_id="10930102",
            creator_name="BlackBoxMods",
            subject="[Sims 4 Mods Manager] Requirements feedback",
            message="Hi @BlackBoxMods,\n\nWe detected missing requirements.",
        )

        assert success is True
        assert "succès" in msg.lower()
        mock_session.post.assert_called_once()
        call_data = mock_session.post.call_args[1]["data"]
        assert call_data["form_submitted"] == "1"
        assert call_data["csrfKey"] == "abc1234567890defabc1234567890def"
        assert call_data["messenger_to"] == "BlackBoxMods"
        assert call_data["messenger_title"] == "[Sims 4 Mods Manager] Requirements feedback"
        assert "Hi @BlackBoxMods" in call_data["messenger_content_noscript"]
        assert "<p>Hi @BlackBoxMods" in call_data["messenger_content"]


def test_loverslab_check_user_already_sent_pm():
    provider = LoversLabProvider()

    messenger_html = """
    <html>
        <body>
            <ul data-role="tableRows">
                <li class="ipsDataItem">
                    <a class="ipsDataItem_title" href="https://www.loverslab.com/messenger/topic/123/">[Sims 4 Mods Manager] Requirements feedback for Confidence Cascade</a>
                    <a href="https://www.loverslab.com/profile/10930102-blackboxmods/">BlackBoxMods</a>
                    <time datetime="2026-09-27T14:00:00Z" title="27/09/2026 à 14:00">Today</time>
                </li>
            </ul>
        </body>
    </html>
    """

    mock_session = MagicMock()
    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.text = messenger_html
    mock_session.get.return_value = mock_get

    with (
        patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True),
        patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session),
    ):
        already_sent, sent_date = provider.check_user_already_sent_pm(
            creator_id="10930102",
            creator_name="BlackBoxMods",
            mod_title="Confidence Cascade",
        )

        assert already_sent is True
        assert sent_date == "27/09/2026 à 14:00"
