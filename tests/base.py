import hashlib
import os
import shutil

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core import files
from core import models as core_models
from plugins.jats_editor import plugin_settings
from submission import models as submission_models
from utils import setting_handler
from utils.testing import helpers

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
TOKEN = "test-token-which-is-not-a-secret"
API = "/plugins/jats-editor/api/v1/"


def fixture_bytes(name):
    with open(os.path.join(FIXTURES, name), "rb") as fh:
        return fh.read()


@override_settings(ROOT_URLCONF="plugins.jats_editor.tests.urls")
class JatsEditorTestCase(TestCase):
    """Press, two journals, an editor, an article in typesetting with one XML
    galley and one figure, and the plugin installed and enabled for the
    first journal with a known token."""

    @classmethod
    def setUpTestData(cls):
        helpers.create_press()
        cls.journal, cls.other_journal = helpers.create_journals()
        helpers.create_roles(["editor", "production", "typesetter", "author"])
        cls.editor = helpers.create_editor(cls.journal)
        plugin_settings.install()
        cls.plugin = plugin_settings.JatsEditorPlugin.get_self()

        cls.article = helpers.create_article(
            cls.journal, stage=submission_models.STAGE_TYPESETTING_PLUGIN
        )
        cls.galley = cls.create_xml_galley(cls.article, cls.editor)
        cls.image = cls.add_image(cls.galley, cls.editor, "fig1.png")

        cls.other_article = helpers.create_article(
            cls.other_journal, stage=submission_models.STAGE_TYPESETTING_PLUGIN
        )
        cls.other_galley = cls.create_xml_galley(cls.other_article, cls.editor)

        cls.set_setting("jats_editor_enabled", "on")
        cls.set_setting("api_token_hash", hashlib.sha256(TOKEN.encode()).hexdigest())
        cls.set_setting("api_account_id", str(cls.editor.pk))
        cls.set_setting("editor_base_url", "https://editor.example.org")

    @classmethod
    def tearDownClass(cls):
        for article in (cls.article, cls.other_article):
            shutil.rmtree(
                os.path.join(settings.BASE_DIR, "files", "articles", str(article.pk)),
                ignore_errors=True,
            )
        super().tearDownClass()

    @classmethod
    def set_setting(cls, name, value, journal=None):
        setting_handler.save_plugin_setting(
            cls.plugin, name, value, journal or cls.journal
        )

    @classmethod
    def create_xml_galley(cls, article, owner, name="article.xml"):
        upload = SimpleUploadedFile(
            name, fixture_bytes("article.xml"), "application/xml"
        )
        file_obj = files.save_file_to_article(
            upload, article, owner, label="XML", is_galley=True
        )
        return core_models.Galley.objects.create(
            article=article, file=file_obj, label="XML", type="xml"
        )

    @classmethod
    def add_image(cls, galley, owner, name):
        upload = SimpleUploadedFile(name, fixture_bytes(name), "image/png")
        image = files.save_file_to_article(
            upload, galley.article, owner, label="Galley Image"
        )
        galley.images.add(image)
        return image

    def api(self, method, path, token=TOKEN, via="header", data=None, **extra):
        url = API + path
        if token is not None and via == "query":
            url += ("&" if "?" in url else "?") + "apiToken=" + token
        elif token is not None:
            extra["HTTP_AUTHORIZATION"] = "Bearer " + token
        call = getattr(self.client, method.lower())
        if data is not None:
            return call(url, data=data, content_type="application/json", **extra)
        return call(url, **extra)
