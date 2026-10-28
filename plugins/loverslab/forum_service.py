"""
LoversLabForumService: Verification of previous comments and submission of comments
on LoversLab mod topics.
"""

import re
import urllib.parse
from typing import List, Tuple, Optional
from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser

from src.core.session_manager import SessionManager
from src.utils.logger import logger


class LoversLabForumService:
    """Service handling interactions with the LoversLab forum/comments system."""

    @staticmethod
    def find_support_topic_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Finds the support topic URL linked from a download file page."""
        # 1. "Get Support" button or link
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True).lower()
            title = (a.get("title") or "").lower()
            if "/topic/" in href and "rules" not in href.lower():
                if "support" in text or "support" in title:
                    full_url = urllib.parse.urljoin(base_url, href)
                    return full_url.split("?")[0]

        # 2. Button leading to a topic
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            classes = a.get("class") or []
            class_str = " ".join(classes).lower()
            if "/topic/" in href and "rules" not in href.lower():
                if "button" in class_str or "btn" in class_str:
                    full_url = urllib.parse.urljoin(base_url, href)
                    return full_url.split("?")[0]

        # 3. Topic pattern /topic/\d+-
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if re.search(r"/topic/\d+-", href) and "rules" not in href.lower():
                full_url = urllib.parse.urljoin(base_url, href)
                return full_url.split("?")[0]

        return None

    @staticmethod
    def _find_comment_form(soup: BeautifulSoup) -> Optional[Tag]:
        """Finds a comment, reply or review form in the page DOM."""
        for form in soup.find_all("form"):
            action = form.get("action", "")
            if "quicksearch" in action or "theme" in action:
                continue

            has_editor = form.find(attrs={"data-role": "contentEditor"}) is not None
            has_reply_flag = form.find("input", {"name": "_contentReply"}) is not None
            has_textarea = form.find("textarea") is not None
            has_comment_input = any(
                "comment" in (inp.get("name") or "").lower() for inp in form.find_all(["input", "textarea"])
            )
            has_action_match = "do=addComment" in action or "do=reply" in action

            if has_editor or has_reply_flag or has_textarea or has_comment_input or has_action_match:
                return form

        return None

    @staticmethod
    def _extract_csrf(soup: BeautifulSoup, html_text: str) -> Optional[str]:
        """Extracts the IPS csrfKey from input or raw HTML script."""
        csrf_input = soup.find("input", {"name": "csrfKey"})
        if csrf_input and csrf_input.get("value"):
            return csrf_input["value"]
        match = re.search(r'csrfKey["\']?\s*[:=]\s*["\']([a-f0-9]{32,})["\']', html_text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def check_user_already_commented(page_url: str, required_keywords: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Scrapes the live LoversLab file or topic page to check if the authenticated user
        has already posted a comment referencing the missing requirements.
        Returns (already_commented: bool, formatted_datetime: Optional[str]).
        """
        if not page_url:
            return False, None

        acc = SessionManager.get_saved_session("loverslab")
        if not acc or not SessionManager.is_member_authenticated("loverslab"):
            return False, None

        cookies = acc.get_cookies_dict()
        member_id = str(cookies.get("ips4_member_id") or "").strip()
        user_display = (acc.user_display_name or "").strip().lower()

        session = SessionManager.get_http_session("loverslab")
        try:
            resp = session.get(page_url, timeout=15)
            if resp.status_code != 200:
                logger.debug(f"check_user_already_commented: HTTP {resp.status_code} on {page_url}")
                return False, None

            soup = BeautifulSoup(resp.text, "html.parser")

            def _search_comments_in_soup(page_soup: BeautifulSoup) -> Tuple[bool, Optional[str]]:
                comment_nodes = page_soup.select(
                    "article.ipsComment, article.cPost, div[id^='comment-'], div[id^='elComment_']"
                )
                for node in comment_nodes:
                    node_author_id = str(node.get("data-memberid") or node.get("data-member-id") or "").strip()
                    author_link = node.select_one("a[href*='/profile/']")
                    author_href = author_link.get("href", "") if author_link else ""
                    author_text = author_link.get_text(strip=True).lower() if author_link else ""

                    is_user = False
                    if member_id and member_id != "0":
                        if node_author_id == member_id or f"/profile/{member_id}-" in author_href:
                            is_user = True
                    if not is_user and user_display and user_display in author_text:
                        is_user = True

                    if not is_user:
                        continue

                    content_node = (
                        node.select_one("[data-role='commentContent']") or node.select_one(".ipsType_richText") or node
                    )
                    content_text = content_node.get_text(separator=" ", strip=True).lower()

                    has_signature = (
                        "requirement" in content_text or "not identified" in content_text or "not found" in content_text
                    )
                    if not has_signature:
                        continue

                    if required_keywords:
                        kw_matched = any(kw.lower().strip() in content_text for kw in required_keywords if kw)
                        if not kw_matched:
                            continue

                    time_node = node.select_one("time")
                    date_str = ""
                    if time_node:
                        raw_date = time_node.get("title") or time_node.get("datetime") or time_node.get_text(strip=True)
                        try:
                            dt = date_parser.parse(raw_date, dayfirst=True)
                            date_str = dt.strftime("%d/%m/%Y à %H:%M")
                        except Exception:
                            date_str = raw_date
                    return True, date_str or "Récemment"

                return False, None

            found, date_str = _search_comments_in_soup(soup)
            if found:
                return True, date_str

            # Check linked discussion topic if page is a file entry
            topic_url = LoversLabForumService.find_support_topic_url(soup, page_url)
            if topic_url:
                try:
                    topic_resp = session.get(topic_url, timeout=12)
                    if topic_resp.status_code == 200:
                        topic_soup = BeautifulSoup(topic_resp.text, "html.parser")
                        found, date_str = _search_comments_in_soup(topic_soup)
                        if found:
                            return True, date_str

                        # If paginated topic, check last page for recent posts
                        last_page_link = topic_soup.select_one(".ipsPagination_last a, li[data-page] a")
                        if last_page_link and last_page_link.get("href"):
                            last_url = urllib.parse.urljoin(topic_url, last_page_link["href"])
                            if last_url != topic_url:
                                last_resp = session.get(last_url, timeout=12)
                                if last_resp.status_code == 200:
                                    last_soup = BeautifulSoup(last_resp.text, "html.parser")
                                    found, date_str = _search_comments_in_soup(last_soup)
                                    if found:
                                        return True, date_str
                except Exception as ex_topic:
                    logger.debug(f"Linked topic check failed for {topic_url}: {ex_topic}")

            return False, None

        except Exception as e:
            logger.debug(f"check_user_already_commented exception for {page_url}: {e}")
            return False, None

    @staticmethod
    def post_mod_comment(page_url: str, message: str) -> Tuple[bool, str]:
        """
        Posts a comment or message on the LoversLab file page or linked discussion topic
        using authenticated IPS session and dynamic form fields.
        """
        if not page_url:
            logger.error("LoversLab post_mod_comment: URL du mod invalide ou manquante.")
            return False, "URL du mod invalide ou manquante."

        if not SessionManager.is_member_authenticated("loverslab"):
            logger.error("LoversLab post_mod_comment: Utilisateur non authentifié avec un compte membre LoversLab.")
            return False, "Utilisateur non authentifié avec un compte membre LoversLab."

        session = SessionManager.get_http_session("loverslab")
        try:
            active_url = page_url
            get_resp = session.get(active_url, timeout=15)
            if get_resp.status_code != 200:
                logger.error(
                    f"LoversLab post_mod_comment: Impossible de charger la page du mod {page_url} (HTTP {get_resp.status_code})"
                )
                return False, f"Impossible de charger la page du mod (Erreur HTTP {get_resp.status_code})."

            html_text = get_resp.text
            soup = BeautifulSoup(html_text, "html.parser")

            form = LoversLabForumService._find_comment_form(soup)

            # If no form on the file page, search for a linked support topic
            if not form:
                topic_url = LoversLabForumService.find_support_topic_url(soup, active_url)
                if topic_url:
                    logger.info(
                        f"LoversLab post_mod_comment: Sujet de discussion trouvé pour {page_url} -> {topic_url}"
                    )
                    topic_resp = session.get(topic_url, timeout=15)
                    if topic_resp.status_code == 200:
                        active_url = topic_url
                        html_text = topic_resp.text
                        soup = BeautifulSoup(html_text, "html.parser")
                        form = LoversLabForumService._find_comment_form(soup)

            # If still not found, check possible ?tab=comments
            if not form and "?tab=" not in active_url:
                tab_url = active_url.rstrip("/") + "/?tab=comments"
                try:
                    tab_resp = session.get(tab_url, timeout=15)
                    if tab_resp.status_code == 200:
                        tab_soup = BeautifulSoup(tab_resp.text, "html.parser")
                        tab_form = LoversLabForumService._find_comment_form(tab_soup)
                        if tab_form:
                            active_url = tab_url
                            html_text = tab_resp.text
                            soup = tab_soup
                            form = tab_form
                except Exception:
                    pass

            if not form:
                csrf_key = LoversLabForumService._extract_csrf(soup, html_text)
                if not csrf_key:
                    logger.error(
                        f"LoversLab post_mod_comment: Aucun formulaire de commentaire ou sujet de support trouvé pour {page_url}"
                    )
                    return (
                        False,
                        "Impossible de trouver le formulaire de commentaire ou le sujet de discussion associé sur LoversLab.",
                    )

                # Fallback to direct ?do=addComment if CSRF exists but no explicit form was matched
                form_action = active_url.rstrip("/") + "/?do=addComment"
                html_message = (
                    "<p>" + message.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
                )
                post_data = {
                    "csrfKey": csrf_key,
                    "comment_value": message,
                    "file_comment_value": message,
                    "comment_value_editor": html_message,
                    "topic_comment": html_message,
                }
            else:
                csrf_key = LoversLabForumService._extract_csrf(soup, html_text)
                if not csrf_key:
                    logger.error(f"LoversLab post_mod_comment: Jeton de sécurité CSRF introuvable sur {active_url}")
                    return False, "Jeton de sécurité CSRF introuvable sur la page LoversLab."

                # Construct dynamic payload from form inputs
                post_data = {}
                for inp in form.find_all("input"):
                    name = inp.get("name")
                    if not name:
                        continue
                    inp_type = (inp.get("type") or "text").lower()
                    val = inp.get("value", "")
                    if inp_type in ["checkbox", "radio"]:
                        if inp.has_attr("checked"):
                            post_data[name] = val or "1"
                    else:
                        post_data[name] = val

                if csrf_key and not post_data.get("csrfKey"):
                    post_data["csrfKey"] = csrf_key

                html_message = (
                    "<p>" + message.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
                )

                textarea_names = []
                for ta in form.find_all("textarea"):
                    ta_name = ta.get("name")
                    if ta_name:
                        textarea_names.append(ta_name)
                        if "noscript" in ta_name.lower():
                            post_data[ta_name] = message
                        else:
                            post_data[ta_name] = html_message

                # Standard and fallback keys
                post_data["comment_value"] = message
                post_data.setdefault("file_comment_value", message)
                post_data.setdefault("comment_value_editor", html_message)
                post_data.setdefault("topic_comment", html_message)

                action = form.get("action", "")
                form_action = urllib.parse.urljoin(active_url, action) if action else active_url

            headers = {
                "Referer": active_url,
                "Origin": "https://www.loverslab.com",
            }

            logger.info(f"LoversLab post_mod_comment: Envoi du message vers {form_action}")
            post_resp = session.post(form_action, data=post_data, headers=headers, timeout=20)
            if post_resp.status_code in [200, 302, 303]:
                if post_resp.status_code == 200:
                    post_soup = BeautifulSoup(post_resp.text, "html.parser")
                    err_box = post_soup.select_one(".ipsMessage_error, .ipsType_warning, [data-role='formError']")
                    if err_box:
                        err_text = err_box.get_text(strip=True)
                        logger.error(
                            f"LoversLab post_mod_comment: Erreur signalée par LoversLab sur {active_url} : {err_text}"
                        )
                        return False, f"Erreur LoversLab: {err_text}"

                logger.info(f"Commentaire publié avec succès sur LoversLab ({active_url}).")
                return True, "Message publié avec succès sur le forum LoversLab."

            if post_resp.status_code == 403:
                logger.error(
                    f"LoversLab post_mod_comment: Accès refusé (403 Cloudflare) sur {form_action} pour {active_url}."
                )
                return False, "Accès refusé par LoversLab (Erreur 403 / Protection Cloudflare)."

            logger.error(
                f"LoversLab post_mod_comment: Erreur HTTP {post_resp.status_code} sur {form_action} pour {active_url}. Réponse : {post_resp.text[:300]}"
            )
            return False, f"Erreur HTTP {post_resp.status_code} lors de la publication du message."

        except Exception as e:
            logger.error(f"Erreur lors de la publication du commentaire sur {page_url}: {e}", exc_info=True)
            return False, f"Exception lors de la publication: {e}"

    @staticmethod
    def extract_creator_info(soup: BeautifulSoup, base_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts the creator's member ID, display name, and profile URL from a mod page.
        Returns (member_id, member_name, profile_url).
        """
        acc = SessionManager.get_saved_session("loverslab")
        my_id = ""
        if acc:
            cookies = acc.get_cookies_dict()
            my_id = str(cookies.get("ips4_member_id") or "").strip()

        candidates = soup.select(
            ".ipsDataItem_author a[href*='/profile/'], .ipsPhotoPanel a[href*='/profile/'], a[href*='/profile/']"
        )
        for a in candidates:
            href = a.get("href", "").strip()
            m = re.search(r"/profile/(\d+)-([^/?#]+)", href)
            if not m:
                continue
            mid = m.group(1)
            slug = m.group(2)
            if my_id and mid == my_id:
                continue

            name = a.get_text(strip=True)
            if not name:
                for sibling in soup.find_all("a", href=href):
                    t = sibling.get_text(strip=True)
                    if t and t.lower() not in ["profile", "find their other files"]:
                        name = t
                        break
            if not name or name.lower() in ["profile", "find their other files"]:
                name = slug.replace("-", " ").strip()

            full_profile_url = urllib.parse.urljoin(base_url, href).split("?")[0]
            if not full_profile_url.endswith("/"):
                full_profile_url += "/"
            return mid, name, full_profile_url

        return None, None, None

    @staticmethod
    def get_creator_info(page_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Fetches the mod page and extracts creator info (member_id, member_name, profile_url).
        """
        if not page_url:
            return None, None, None
        session = SessionManager.get_http_session("loverslab")
        try:
            resp = session.get(page_url, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                return LoversLabForumService.extract_creator_info(soup, page_url)
        except Exception as e:
            logger.debug(f"get_creator_info failed for {page_url}: {e}")
        return None, None, None

    @staticmethod
    def check_user_already_sent_pm(
        creator_id: Optional[str] = None,
        creator_name: Optional[str] = None,
        mod_title: str = "",
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks the user's LoversLab messenger (/messenger/) to determine if a PM
        has already been sent regarding this mod or to this creator.
        Returns (already_sent: bool, formatted_date: Optional[str]).
        """
        if not SessionManager.is_member_authenticated("loverslab"):
            return False, None

        session = SessionManager.get_http_session("loverslab")
        try:
            resp = session.get("https://www.loverslab.com/messenger/", timeout=15)
            if resp.status_code != 200:
                return False, None

            soup = BeautifulSoup(resp.text, "html.parser")
            norm_title = mod_title.lower().strip() if mod_title else ""
            norm_creator = creator_name.lower().strip() if creator_name else ""

            for item in soup.select("li.ipsDataItem, tr.ipsDataItem, [data-role='tableRows'] > *"):
                text = item.get_text(separator=" ", strip=True).lower()
                title_elem = item.select_one(".ipsDataItem_title, a[href*='/messenger/topic/']")
                item_title = title_elem.get_text(strip=True).lower() if title_elem else ""

                matches_mod = norm_title and (norm_title in item_title or norm_title in text)
                matches_creator = False
                if creator_id and f"/profile/{creator_id}-" in str(item):
                    matches_creator = True
                elif norm_creator and norm_creator in text:
                    matches_creator = True

                if matches_mod or (matches_creator and "sims 4 mods manager" in text):
                    time_elem = item.select_one("time")
                    date_str = ""
                    if time_elem:
                        raw_date = time_elem.get("title") or time_elem.get("datetime") or time_elem.get_text(strip=True)
                        try:
                            dt = date_parser.parse(raw_date, dayfirst=True)
                            date_str = dt.strftime("%d/%m/%Y à %H:%M")
                        except Exception:
                            date_str = raw_date
                    return True, date_str or "Récemment"

            return False, None
        except Exception as e:
            logger.debug(f"check_user_already_sent_pm error: {e}")
            return False, None

    @staticmethod
    def send_private_message(
        creator_id: str,
        creator_name: str,
        subject: str,
        message: str,
    ) -> Tuple[bool, str]:
        """
        Sends a private message to a LoversLab creator via LoversLab Messenger.
        """
        if not creator_id:
            logger.error("LoversLab send_private_message: ID du créateur manquant.")
            return False, "ID du créateur manquant."

        if not SessionManager.is_member_authenticated("loverslab"):
            logger.error("LoversLab send_private_message: Utilisateur non authentifié.")
            return False, "Utilisateur non authentifié avec un compte membre LoversLab."

        session = SessionManager.get_http_session("loverslab")
        compose_url = f"https://www.loverslab.com/messenger/compose/?to={creator_id}"

        try:
            get_resp = session.get(compose_url, timeout=15)
            if get_resp.status_code != 200:
                logger.error(
                    f"LoversLab send_private_message: Impossible de charger la page de messagerie {compose_url} (HTTP {get_resp.status_code})"
                )
                return False, f"Impossible de charger la messagerie LoversLab (HTTP {get_resp.status_code})."

            html_text = get_resp.text
            soup = BeautifulSoup(html_text, "html.parser")

            csrf_key = LoversLabForumService._extract_csrf(soup, html_text)
            if not csrf_key:
                logger.error(f"LoversLab send_private_message: Jeton CSRF introuvable sur {compose_url}")
                return False, "Jeton de sécurité CSRF introuvable sur LoversLab."

            form = soup.find("form", class_=lambda c: c and "ipsForm" in c)
            post_data = {
                "form_submitted": "1",
                "csrfKey": csrf_key,
                "messenger_to": creator_name or "",
                "messenger_title": subject or "[Sims 4 Mods Manager] Requirements feedback",
            }

            if form:
                for inp in form.find_all("input"):
                    name = inp.get("name")
                    val = inp.get("value", "")
                    if name and name not in post_data:
                        post_data[name] = val

                to_elem = form.find(attrs={"name": "messenger_to"})
                if to_elem and to_elem.get_text(strip=True):
                    post_data["messenger_to"] = to_elem.get_text(strip=True)

            html_message = (
                "<p>" + message.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
            )
            post_data["messenger_content_noscript"] = message
            post_data["messenger_content"] = html_message

            action = form.get("action", "") if form else ""
            target_url = urllib.parse.urljoin(compose_url, action) if action else compose_url

            headers = {
                "Referer": compose_url,
                "Origin": "https://www.loverslab.com",
            }

            logger.info(f"LoversLab send_private_message: Envoi du MP à '{creator_name}' (ID {creator_id})")
            post_resp = session.post(target_url, data=post_data, headers=headers, timeout=20)

            if post_resp.status_code in [200, 302, 303]:
                if post_resp.status_code == 200:
                    post_soup = BeautifulSoup(post_resp.text, "html.parser")
                    err_box = post_soup.select_one(".ipsMessage_error, .ipsType_warning, [data-role='formError']")
                    if err_box:
                        err_text = err_box.get_text(strip=True)
                        logger.error(f"LoversLab send_private_message: Erreur signalée par LoversLab : {err_text}")
                        return False, f"Erreur LoversLab: {err_text}"

                logger.info(f"Message privé envoyé avec succès à {creator_name} ({creator_id}).")
                return True, "Message privé envoyé avec succès au créateur sur LoversLab."

            if post_resp.status_code == 403:
                logger.error("LoversLab send_private_message: Accès refusé (403 Cloudflare).")
                return False, "Accès refusé par LoversLab (Erreur 403 / Protection Cloudflare)."

            logger.error(
                f"LoversLab send_private_message: Erreur HTTP {post_resp.status_code}. Réponse: {post_resp.text[:300]}"
            )
            return False, f"Erreur HTTP {post_resp.status_code} lors de l'envoi du message privé."

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du MP sur LoversLab: {e}", exc_info=True)
            return False, f"Exception lors de l'envoi du message: {e}"

    @staticmethod
    def delete_user_comment(page_url: str, required_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
        """
        Finds and deletes (or hides/clears) the authenticated user's requirements report comment
        on the LoversLab file page or linked support topic.
        Returns (success: bool, message: str).
        """
        if not page_url:
            return False, "URL du mod invalide ou manquante."

        acc = SessionManager.get_saved_session("loverslab")
        if not acc or not SessionManager.is_member_authenticated("loverslab"):
            return False, "Utilisateur non authentifié avec un compte membre LoversLab."

        cookies = acc.get_cookies_dict()
        member_id = str(cookies.get("ips4_member_id") or "").strip()
        user_display = (acc.user_display_name or "").strip().lower()
        session = SessionManager.get_http_session("loverslab")

        def _find_matching_comment_node(page_soup: BeautifulSoup) -> Optional[Tag]:
            comment_nodes = page_soup.select(
                "article.ipsComment, article.cPost, div[id^='comment-'], div[id^='elComment_']"
            )
            for node in reversed(comment_nodes):
                node_author_id = str(node.get("data-memberid") or node.get("data-member-id") or "").strip()
                author_link = node.select_one("a[href*='/profile/']")
                author_href = author_link.get("href", "") if author_link else ""
                author_text = author_link.get_text(strip=True).lower() if author_link else ""

                is_user = False
                if member_id and member_id != "0":
                    if node_author_id == member_id or f"/profile/{member_id}-" in author_href:
                        is_user = True
                if not is_user and user_display and user_display in author_text:
                    is_user = True
                if not is_user:
                    continue

                content_node = (
                    node.select_one("[data-role='commentContent']") or node.select_one(".ipsType_richText") or node
                )
                content_text = content_node.get_text(separator=" ", strip=True).lower()
                has_signature = (
                    "requirement" in content_text or "not identified" in content_text or "not found" in content_text
                )
                if not has_signature:
                    continue

                if required_keywords:
                    kw_matched = any(kw.lower().strip() in content_text for kw in required_keywords if kw)
                    if not kw_matched:
                        continue

                return node
            return None

        def _extract_comment_id(node: Tag) -> Optional[str]:
            for attr in ("data-commentid", "data-comment-id"):
                val = node.get(attr)
                if val and str(val).isdigit():
                    return str(val)
            node_id = str(node.get("id") or "")
            m = re.search(r"(?:elComment_|comment-)(\d+)", node_id)
            if m:
                return m.group(1)
            for a in node.find_all("a", href=True):
                m_href = re.search(r"[?&]comment=(\d+)", a["href"])
                if m_href:
                    return m_href.group(1)
            return None

        try:
            resp = session.get(page_url, timeout=15)
            if resp.status_code != 200:
                return False, f"Impossible de charger la page du mod (HTTP {resp.status_code})."

            active_url = page_url
            active_html = resp.text
            active_soup = BeautifulSoup(active_html, "html.parser")
            target_node = _find_matching_comment_node(active_soup)

            if not target_node:
                topic_url = LoversLabForumService.find_support_topic_url(active_soup, page_url)
                if topic_url:
                    topic_resp = session.get(topic_url, timeout=15)
                    if topic_resp.status_code == 200:
                        active_url = topic_url
                        active_html = topic_resp.text
                        active_soup = BeautifulSoup(active_html, "html.parser")
                        target_node = _find_matching_comment_node(active_soup)

                        if not target_node:
                            last_page_link = active_soup.select_one(".ipsPagination_last a, li[data-page] a")
                            if last_page_link and last_page_link.get("href"):
                                last_url = urllib.parse.urljoin(topic_url, last_page_link["href"])
                                if last_url != topic_url:
                                    last_resp = session.get(last_url, timeout=15)
                                    if last_resp.status_code == 200:
                                        active_url = last_url
                                        active_html = last_resp.text
                                        active_soup = BeautifulSoup(active_html, "html.parser")
                                        target_node = _find_matching_comment_node(active_soup)

            if not target_node:
                return False, "Aucun commentaire correspondant de l'utilisateur trouvé sur le forum."

            comment_id = _extract_comment_id(target_node)
            csrf_key = LoversLabForumService._extract_csrf(active_soup, active_html)
            if not comment_id or not csrf_key:
                return False, "Impossible d'extraire l'identifiant du commentaire ou le jeton CSRF."

            base_clean_url = active_url.split("?")[0].rstrip("/") + "/"
            headers = {
                "Referer": active_url,
                "Origin": "https://www.loverslab.com",
                "X-Requested-With": "XMLHttpRequest",
            }

            # 1. Try direct deleteComment or hideComment link from DOM or standard IPS4 endpoint
            delete_href = None
            for a in target_node.find_all("a", href=True):
                if "do=deleteComment" in a["href"] or "do=hideComment" in a["href"]:
                    delete_href = urllib.parse.urljoin(active_url, a["href"])
                    break

            candidate_urls = []
            if delete_href:
                candidate_urls.append(delete_href)
            candidate_urls.append(f"{base_clean_url}?do=deleteComment&comment={comment_id}&csrfKey={csrf_key}")
            candidate_urls.append(f"{base_clean_url}?do=hideComment&comment={comment_id}&csrfKey={csrf_key}")

            for del_url in candidate_urls:
                del_resp = session.post(
                    del_url,
                    data={"csrfKey": csrf_key, "hide_reason": "Test automated cleanup", "form_submitted": "1"},
                    headers=headers,
                    timeout=15,
                )
                if del_resp.status_code in [200, 302, 303]:
                    already_there, _ = LoversLabForumService.check_user_already_commented(
                        page_url, required_keywords or []
                    )
                    if not already_there:
                        logger.info(f"Commentaire #{comment_id} supprimé avec succès sur LoversLab ({base_clean_url}).")
                        return True, f"Commentaire #{comment_id} supprimé avec succès du forum."

            # 2. Fallback: editComment to sanitize content if hard-delete is restricted on the board
            edit_url = f"{base_clean_url}?do=editComment&comment={comment_id}"
            edit_data = {
                "csrfKey": csrf_key,
                "form_submitted": "1",
                "comment_value": "[Deleted]",
                f"comment_value_{comment_id}": "<p>[Deleted]</p>",
                f"topic_comment_{comment_id}": "<p>[Deleted]</p>",
            }
            edit_resp = session.post(edit_url, data=edit_data, headers=headers, timeout=15)
            if edit_resp.status_code in [200, 302, 303]:
                logger.info(f"Commentaire #{comment_id} nettoyé/supprimé via édition sur LoversLab ({base_clean_url}).")
                return True, f"Commentaire #{comment_id} supprimé/nettoyé avec succès."

            return False, f"Échec de la suppression du commentaire #{comment_id}."
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du commentaire sur {page_url}: {e}", exc_info=True)
            return False, f"Exception lors de la suppression du commentaire: {e}"
