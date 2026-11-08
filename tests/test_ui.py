import hashlib
from urllib.parse import parse_qs, urlparse

from django.conf import settings as django_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core import files, plugin_loader
from plugins.jats_editor import config, hooks, plugin_settings
from plugins.jats_editor.tests.base import JatsEditorTestCase, fixture_bytes
from utils.testing import helpers

UI = "/plugins/jats-editor/"


class ManagerPageTests(JatsEditorTestCase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(UI + "manager/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_regular_user_is_denied(self):
        user = helpers.create_regular_user()
        self.client.force_login(user)
        self.assertEqual(self.client.get(UI + "manager/").status_code, 403)

    def test_editor_sees_current_settings(self):
        self.client.force_login(self.editor)
        response = self.client.get(UI + "manager/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://editor.example.org")
        self.assertContains(response, self.editor.email)

    def test_manager_url_name_matches_plugin_settings(self):
        self.assertEqual(reverse(plugin_settings.MANAGER_URL), UI + "manager/")

    def test_editor_can_save_settings(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            UI + "manager/",
            {
                "action": "save",
                "enabled": "on",
                "editor_base_url": "https://pubready.example.org/",
                "max_upload_mb": "40",
                "api_account": str(self.editor.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            config.editor_base_url(self.journal), "https://pubready.example.org"
        )
        self.assertEqual(config.max_upload_bytes(self.journal), 40 * 1024 * 1024)
        self.assertEqual(config.service_account(self.journal), self.editor)
        self.assertTrue(config.is_enabled(self.journal))

    def test_unchecking_enabled_disables_api(self):
        self.client.force_login(self.editor)
        self.client.post(
            UI + "manager/",
            {
                "action": "save",
                "editor_base_url": "",
                "max_upload_mb": "25",
                "api_account": str(self.editor.pk),
            },
        )
        self.assertFalse(config.is_enabled(self.journal))
        self.assertEqual(self.api("get", "ping/").status_code, 403)

    def test_rejects_invalid_settings(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            UI + "manager/",
            {
                "action": "save",
                "editor_base_url": "not a url",
                "max_upload_mb": "0",
                "api_account": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            config.editor_base_url(self.journal), "https://editor.example.org"
        )

    def test_rotate_token_shows_it_once_and_stores_only_the_hash(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            UI + "manager/", {"action": "rotate_token"}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        token = response.context["new_token"]
        self.assertGreaterEqual(len(token), 32)
        self.assertContains(response, token)
        self.assertEqual(
            config.token_hash(self.journal), hashlib.sha256(token.encode()).hexdigest()
        )
        self.assertEqual(self.api("get", "ping/", token=token).status_code, 200)
        self.assertNotContains(self.client.get(UI + "manager/"), token)

    def test_revoke_token_disables_old_token(self):
        self.client.force_login(self.editor)
        self.client.post(UI + "manager/", {"action": "revoke_token"})
        self.assertEqual(config.token_hash(self.journal), "")
        self.assertEqual(self.api("get", "ping/").status_code, 401)

    def test_post_requires_csrf_token(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.editor)
        response = client.post(UI + "manager/", {"action": "revoke_token"})
        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(config.token_hash(self.journal), "")


class GalleyListTests(JatsEditorTestCase):
    def test_lists_xml_galleys_with_open_links(self):
        self.client.force_login(self.editor)
        response = self.client.get(UI + "galleys/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)
        self.assertContains(
            response, UI + "open/%d/galley/%d/" % (self.article.pk, self.galley.pk)
        )
        self.assertNotContains(
            response,
            "open/%d/galley/%d/" % (self.other_article.pk, self.other_galley.pk),
        )

    def test_regular_user_is_denied(self):
        self.client.force_login(helpers.create_regular_user())
        self.assertEqual(self.client.get(UI + "galleys/").status_code, 403)


class OpenInEditorTests(JatsEditorTestCase):
    def test_redirects_editor_to_pubready_with_galley_context(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            UI + "open/%d/galley/%d/" % (self.article.pk, self.galley.pk)
        )
        self.assertEqual(response.status_code, 302)
        target = urlparse(response["Location"])
        self.assertEqual(
            "%s://%s%s" % (target.scheme, target.netloc, target.path),
            "https://editor.example.org/janeway/open",
        )
        query = parse_qs(target.query)
        self.assertEqual(query["host"], [self.journal.site_url()])
        self.assertEqual(query["journal"], [self.journal.code])
        self.assertEqual(query["article"], [str(self.article.pk)])
        self.assertEqual(query["galley"], [str(self.galley.pk)])

    def test_redirects_with_file_context_for_manuscript_xml(self):
        upload = SimpleUploadedFile(
            "draft.xml", fixture_bytes("article.xml"), "application/xml"
        )
        manuscript = files.save_file_to_article(
            upload, self.article, self.editor, label="Manuscript"
        )
        self.article.manuscript_files.add(manuscript)
        self.client.force_login(self.editor)
        response = self.client.get(
            UI + "open/%d/file/%d/" % (self.article.pk, manuscript.pk)
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            parse_qs(urlparse(response["Location"]).query)["file"], [str(manuscript.pk)]
        )

    def test_galley_of_other_journal_is_not_found(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            UI + "open/%d/galley/%d/" % (self.other_article.pk, self.other_galley.pk)
        )
        self.assertEqual(response.status_code, 404)

    def test_without_editor_url_falls_back_to_manager(self):
        self.set_setting("editor_base_url", "")
        self.client.force_login(self.editor)
        response = self.client.get(
            UI + "open/%d/galley/%d/" % (self.article.pk, self.galley.pk)
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith(UI + "manager/"))

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(
            UI + "open/%d/galley/%d/" % (self.article.pk, self.galley.pk)
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])


class HookTests(JatsEditorTestCase):
    def setUp(self):
        super().setUp()
        self.request = self.client.get(UI + "manager/").wsgi_request
        self.request.journal = self.journal
        self.context = {"request": self.request}

    def test_registry_is_loadable(self):
        plugin_loader.register_hooks([plugin_settings.hook_registry()])
        self.assertIn("conversion_row", django_settings.PLUGIN_HOOKS)
        self.assertIn("journal_editor_nav_block", django_settings.PLUGIN_HOOKS)

    def test_conversion_row_links_xml_manuscript_files(self):
        upload = SimpleUploadedFile(
            "draft.xml", fixture_bytes("article.xml"), "application/xml"
        )
        manuscript = files.save_file_to_article(
            upload, self.article, self.editor, label="Manuscript"
        )
        html = hooks.conversion_row(self.context, manuscript, self.article)
        self.assertIn("open/%d/file/%d/" % (self.article.pk, manuscript.pk), html)
        self.assertIn("<tr", html)

    def test_conversion_row_ignores_non_xml_files(self):
        upload = SimpleUploadedFile("draft.txt", b"plain", "text/plain")
        other = files.save_file_to_article(
            upload, self.article, self.editor, label="Manuscript"
        )
        self.assertEqual(hooks.conversion_row(self.context, other, self.article), "")

    def test_conversion_row_is_empty_when_disabled(self):
        self.set_setting("jats_editor_enabled", "")
        html = hooks.conversion_row(self.context, self.galley.file, self.article)
        self.assertEqual(html, "")

    def test_nav_block_links_galley_list(self):
        html = hooks.editor_nav_block(self.context)
        self.assertIn(UI + "galleys/", html)

    def test_nav_block_is_empty_when_disabled(self):
        self.set_setting("jats_editor_enabled", "")
        self.assertEqual(hooks.editor_nav_block(self.context), "")
