from django.core.files.uploadedfile import SimpleUploadedFile

from core import files
from plugins.jats_editor.tests.base import JatsEditorTestCase, fixture_bytes
from submission import models as submission_models


class JournalMetadataTests(JatsEditorTestCase):
    def test_returns_journal_metadata_in_ojs_shape(self):
        response = self.api("get", "journal-metadata/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        metadata = body["metadata"]
        self.assertEqual(metadata["id"], self.journal.pk)
        self.assertEqual(metadata["urlPath"], self.journal.code)
        self.assertEqual(metadata["slug"], self.journal.code)
        self.assertEqual(metadata["name"], self.journal.name)
        self.assertEqual(metadata["onlineIssn"], self.journal.issn)
        self.assertEqual(metadata["janewayUrl"], self.journal.site_url())
        self.assertEqual(metadata["ojsUrl"], metadata["janewayUrl"])
        self.assertEqual(
            metadata["names"], {metadata["primaryLocale"]: self.journal.name}
        )

    def test_requires_token(self):
        self.assertEqual(
            self.api("get", "journal-metadata/", token=None).status_code, 401
        )


class ArticleListTests(JatsEditorTestCase):
    def test_lists_only_articles_of_the_current_journal(self):
        response = self.api("get", "articles/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = [item["id"] for item in body["items"]]
        self.assertIn(self.article.pk, ids)
        self.assertNotIn(self.other_article.pk, ids)
        self.assertEqual(body["itemsMax"], len(ids))

    def test_item_shape(self):
        item = next(
            i
            for i in self.api("get", "articles/").json()["items"]
            if i["id"] == self.article.pk
        )
        self.assertEqual(item["title"], self.article.title)
        self.assertEqual(item["stage"], submission_models.STAGE_TYPESETTING_PLUGIN)
        self.assertEqual(item["galleyCount"], 1)
        self.assertIsInstance(item["authors"], list)

    def test_filters_by_stage(self):
        response = self.api("get", "articles/?stages=Published")
        self.assertEqual(response.json()["items"], [])
        response = self.api(
            "get",
            "articles/?stages=Published,%s"
            % submission_models.STAGE_TYPESETTING_PLUGIN,
        )
        self.assertEqual([i["id"] for i in response.json()["items"]], [self.article.pk])

    def test_paginates(self):
        second = self.create_article(title="Second")
        response = self.api("get", "articles/?limit=1&offset=0")
        body = response.json()
        self.assertEqual(body["itemsMax"], 2)
        self.assertEqual(len(body["items"]), 1)
        response = self.api("get", "articles/?limit=1&offset=1")
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertNotEqual(body["items"][0]["id"], response.json()["items"][0]["id"])
        self.assertEqual(self.api("get", "articles/?limit=abc").status_code, 400)
        second.delete()

    def create_article(self, **kwargs):
        from utils.testing import helpers

        return helpers.create_article(
            self.journal, stage=submission_models.STAGE_TYPESETTING_PLUGIN, **kwargs
        )


class ArticleDetailTests(JatsEditorTestCase):
    def test_returns_article_with_galleys(self):
        response = self.api("get", "article/%d/" % self.article.pk)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], self.article.pk)
        self.assertEqual(body["title"], self.article.title)
        self.assertEqual(len(body["galleys"]), 1)
        galley = body["galleys"][0]
        self.assertEqual(galley["id"], self.galley.pk)
        self.assertEqual(galley["type"], "xml")
        self.assertEqual(galley["fileId"], self.galley.file.pk)
        self.assertEqual(galley["fileName"], "article.xml")
        self.assertIn(galley["mimeType"], files.XML_MIMETYPES)
        self.assertEqual(galley["images"][0]["fileId"], self.image.pk)

    def test_article_of_other_journal_is_not_found(self):
        response = self.api("get", "article/%d/" % self.other_article.pk)
        self.assertEqual(response.status_code, 404)

    def test_unknown_article_is_not_found(self):
        self.assertEqual(self.api("get", "article/999999/").status_code, 404)


class WorkflowFilesTests(JatsEditorTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        upload = SimpleUploadedFile(
            "draft.xml", fixture_bytes("article.xml"), "application/xml"
        )
        cls.manuscript = files.save_file_to_article(
            upload, cls.article, cls.editor, label="Manuscript"
        )
        cls.article.manuscript_files.add(cls.manuscript)

    def test_production_stage_lists_galleys_and_their_images(self):
        response = self.api("get", "workflow-files/%d/?stages=5" % self.article.pk)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["submissionId"], self.article.pk)
        by_id = {f["id"]: f for f in body["files"]}
        self.assertIn(self.galley.file.pk, by_id)
        self.assertIn(self.image.pk, by_id)
        self.assertNotIn(self.manuscript.pk, by_id)
        galley_file = by_id[self.galley.file.pk]
        self.assertEqual(galley_file["fileStage"], 10)
        self.assertEqual(galley_file["galleyId"], self.galley.pk)
        self.assertEqual(galley_file["name"], "article.xml")
        self.assertIn(galley_file["mimetype"], files.XML_MIMETYPES)
        self.assertFalse(galley_file["isDependent"])
        image = by_id[self.image.pk]
        self.assertTrue(image["isDependent"])
        self.assertEqual(image["parentFileId"], self.galley.file.pk)
        self.assertEqual(image["fileStage"], 17)

    def test_copyediting_stage_lists_manuscript_files(self):
        body = self.api("get", "workflow-files/%d/?stages=4" % self.article.pk).json()
        ids = [f["id"] for f in body["files"]]
        self.assertEqual(ids, [self.manuscript.pk])
        self.assertEqual(body["files"][0]["fileStage"], 9)

    def test_default_lists_both_stages(self):
        body = self.api("get", "workflow-files/%d/" % self.article.pk).json()
        ids = {f["id"] for f in body["files"]}
        self.assertEqual(ids, {self.manuscript.pk, self.galley.file.pk, self.image.pk})

    def test_article_of_other_journal_is_not_found(self):
        response = self.api("get", "workflow-files/%d/" % self.other_article.pk)
        self.assertEqual(response.status_code, 404)

    def test_download_streams_file_content(self):
        response = self.api(
            "get",
            "workflow-files/%d/%d/download/" % (self.article.pk, self.galley.file.pk),
        )
        self.assertEqual(response.status_code, 200)
        content = (
            b"".join(response.streaming_content)
            if response.streaming
            else response.content
        )
        self.assertEqual(content, fixture_bytes("article.xml"))

    def test_download_rejects_file_from_another_article(self):
        response = self.api(
            "get",
            "workflow-files/%d/%d/download/"
            % (self.article.pk, self.other_galley.file.pk),
        )
        self.assertEqual(response.status_code, 404)
