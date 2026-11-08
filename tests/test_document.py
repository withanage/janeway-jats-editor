import base64
import json
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from core import files
from core import models as core_models
from plugins.jats_editor.tests.base import API, TOKEN, JatsEditorTestCase, fixture_bytes
from submission import models as submission_models
from utils.testing import helpers

NEW_XML = (
    fixture_bytes("article.xml")
    .decode("utf-8")
    .replace("<article-title>", "<article-title>Edited ")
)


def data_uri(payload, mime="image/png"):
    return "data:%s;base64,%s" % (mime, base64.b64encode(payload).decode("ascii"))


class DocumentGetTests(JatsEditorTestCase):
    def test_returns_dar_for_xml_galley(self):
        response = self.api("get", "document/%d/" % self.galley.pk)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["version"], 1)
        self.assertEqual(
            body["resources"]["manuscript.xml"]["data"],
            fixture_bytes("article.xml").decode("utf-8"),
        )
        media = body["resources"]["fig1.png"]
        self.assertEqual(media["encoding"], "url")
        expected = "http://testserver%smedia/%d/%d/" % (
            API,
            self.galley.pk,
            self.image.pk,
        )
        self.assertTrue(media["data"].startswith(expected), media["data"])
        self.assertIn("apiToken=" + TOKEN, media["data"])

    def test_media_url_is_fetchable(self):
        url = self.api("get", "document/%d/" % self.galley.pk).json()["resources"][
            "fig1.png"
        ]["data"]
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_xml_galley_is_unsupported(self):
        upload = SimpleUploadedFile("paper.txt", b"not xml at all", "text/plain")
        file_obj = files.save_file_to_article(
            upload, self.article, self.editor, is_galley=True
        )
        galley = core_models.Galley.objects.create(
            article=self.article, file=file_obj, label="TXT", type="pdf"
        )
        self.assertEqual(self.api("get", "document/%d/" % galley.pk).status_code, 415)

    def test_malformed_xml_galley_is_unprocessable(self):
        upload = SimpleUploadedFile(
            "broken.xml", b"<article><body></article>", "application/xml"
        )
        file_obj = files.save_file_to_article(
            upload, self.article, self.editor, is_galley=True
        )
        galley = core_models.Galley.objects.create(
            article=self.article, file=file_obj, label="XML", type="xml"
        )
        self.assertEqual(self.api("get", "document/%d/" % galley.pk).status_code, 422)

    def test_galley_of_other_journal_is_not_found(self):
        self.assertEqual(
            self.api("get", "document/%d/" % self.other_galley.pk).status_code, 404
        )


class DocumentPutTests(JatsEditorTestCase):
    def put(self, galley=None, **body):
        galley = galley or self.galley
        return self.api("put", "document/%d/" % galley.pk, data=json.dumps(body))

    def test_overwrites_galley_file_keeping_history(self):
        before = self.galley.file.history.count()
        response = self.put(jatsXml=NEW_XML)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["fileId"], self.galley.file.pk)
        self.assertEqual(body["galleyId"], self.galley.pk)
        self.assertEqual(body["dependentFiles"], [])
        self.galley.refresh_from_db()
        self.assertEqual(self.galley.file.history.count(), before + 1)
        self.assertEqual(body["historyCount"], before + 1)
        self.assertEqual(files.get_file(self.galley.file, self.article), NEW_XML)
        self.assertEqual(self.galley.file.original_filename, "article.xml")
        self.assertIn(self.galley.file.mime_type, files.XML_MIMETYPES)
        self.assertEqual(self.galley.file.owner, self.editor)

    def test_accepts_legacy_resources_body(self):
        response = self.put(resources={"manuscript.xml": {"data": NEW_XML}})
        self.assertEqual(response.status_code, 200)
        self.galley.refresh_from_db()
        self.assertEqual(files.get_file(self.galley.file, self.article), NEW_XML)

    def test_updates_existing_image_and_creates_new_one(self):
        before = self.image.history.count()
        response = self.put(
            jatsXml=NEW_XML,
            images=[
                {"filename": "fig1.png", "data": data_uri(fixture_bytes("fig1.png"))},
                {
                    "filename": "fig2.png",
                    "data": base64.b64encode(fixture_bytes("fig1.png")).decode(),
                },
            ],
        )
        self.assertEqual(response.status_code, 200, response.content)
        dependent = {d["filename"]: d for d in response.json()["dependentFiles"]}
        self.assertEqual(dependent["fig1.png"]["status"], "updated")
        self.assertEqual(dependent["fig1.png"]["submissionFileId"], self.image.pk)
        self.assertEqual(dependent["fig2.png"]["status"], "created")
        self.assertEqual(self.galley.images.count(), 2)
        self.image.refresh_from_db()
        self.assertEqual(self.image.history.count(), before + 1)
        created = self.galley.images.get(pk=dependent["fig2.png"]["submissionFileId"])
        self.assertEqual(created.original_filename, "fig2.png")
        self.assertEqual(created.mime_type, "image/png")
        self.assertEqual(created.owner, self.editor)

    def test_image_filename_is_reduced_to_basename(self):
        response = self.put(
            jatsXml=NEW_XML,
            images=[
                {
                    "filename": "../../../etc/evil.png",
                    "data": data_uri(fixture_bytes("fig1.png")),
                }
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dependentFiles"][0]["filename"], "evil.png")
        self.assertTrue(
            self.galley.images.filter(original_filename="evil.png").exists()
        )

    def test_rejects_image_without_filename(self):
        response = self.put(
            jatsXml=NEW_XML, images=[{"filename": "", "data": data_uri(b"x")}]
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_image_payload(self):
        response = self.put(
            jatsXml=NEW_XML,
            images=[
                {"filename": "fig9.png", "data": data_uri(b"<html>not an image</html>")}
            ],
        )
        self.assertEqual(response.status_code, 415)
        self.assertFalse(
            self.galley.images.filter(original_filename="fig9.png").exists()
        )

    def test_rejects_undecodable_image(self):
        response = self.put(
            jatsXml=NEW_XML, images=[{"filename": "fig9.png", "data": "***"}]
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_empty_manuscript(self):
        self.assertEqual(self.put(jatsXml="").status_code, 400)
        self.assertEqual(self.put().status_code, 400)

    def test_rejects_invalid_json(self):
        response = self.api("put", "document/%d/" % self.galley.pk, data="{not json")
        self.assertEqual(response.status_code, 400)

    def test_rejects_malformed_xml_without_touching_file(self):
        before = self.galley.file.history.count()
        self.assertEqual(self.put(jatsXml="<article>").status_code, 422)
        self.assertEqual(self.galley.file.history.count(), before)

    def test_rejects_oversized_manuscript(self):
        self.set_setting("max_upload_mb", "1")
        padding = "<!-- %s -->" % ("x" * (1024 * 1024 + 10))
        response = self.put(
            jatsXml=NEW_XML.replace("</article>", padding + "</article>")
        )
        self.assertEqual(response.status_code, 413)

    def test_non_xml_galley_is_unsupported(self):
        upload = SimpleUploadedFile("paper.txt", b"plain", "text/plain")
        file_obj = files.save_file_to_article(
            upload, self.article, self.editor, is_galley=True
        )
        galley = core_models.Galley.objects.create(
            article=self.article, file=file_obj, label="TXT", type="pdf"
        )
        self.assertEqual(self.put(galley=galley, jatsXml=NEW_XML).status_code, 415)

    def test_galley_of_other_journal_is_not_found(self):
        self.assertEqual(
            self.put(galley=self.other_galley, jatsXml=NEW_XML).status_code, 404
        )


class MediaTests(JatsEditorTestCase):
    def test_get_returns_image_bytes(self):
        response = self.api("get", "media/%d/%d/" % (self.galley.pk, self.image.pk))
        self.assertEqual(response.status_code, 200)
        content = (
            b"".join(response.streaming_content)
            if response.streaming
            else response.content
        )
        self.assertEqual(content, fixture_bytes("fig1.png"))

    def test_get_rejects_image_not_attached_to_galley(self):
        other = self.add_image(self.other_galley, self.editor, "fig1.png")
        response = self.api("get", "media/%d/%d/" % (self.galley.pk, other.pk))
        self.assertEqual(response.status_code, 404)

    def test_post_creates_image(self):
        response = self.api(
            "post",
            "media/%d/" % self.galley.pk,
            data=json.dumps(
                {
                    "media": {
                        "fileName": "fig3.png",
                        "data": data_uri(fixture_bytes("fig1.png")),
                    }
                }
            ),
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertTrue(body["success"])
        image = self.galley.images.get(pk=body["submissionFileId"])
        self.assertEqual(body["fileId"], image.pk)
        self.assertEqual(image.original_filename, "fig3.png")

    def test_post_with_same_name_overwrites(self):
        before = self.image.history.count()
        response = self.api(
            "post",
            "media/%d/" % self.galley.pk,
            data=json.dumps(
                {"fileName": "fig1.png", "data": data_uri(fixture_bytes("fig1.png"))}
            ),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["submissionFileId"], self.image.pk)
        self.image.refresh_from_db()
        self.assertEqual(self.image.history.count(), before + 1)
        self.assertEqual(self.galley.images.count(), 1)

    def test_post_rejects_missing_data(self):
        response = self.api(
            "post", "media/%d/" % self.galley.pk, data=json.dumps({"fileName": "x.png"})
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_removes_image_and_its_file(self):
        # A dedicated image: the shared fixture image must stay on disk for other tests.
        image = self.add_image(self.galley, self.editor, "fig1.png")
        path = image.self_article_path()
        response = self.api("delete", "media/%d/%d/" % (self.galley.pk, image.pk))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.galley.images.filter(pk=image.pk).exists())
        self.assertFalse(core_models.File.objects.filter(pk=image.pk).exists())
        self.assertFalse(os.path.exists(path))

    def test_delete_rejects_galley_file_itself(self):
        response = self.api(
            "delete", "media/%d/%d/" % (self.galley.pk, self.galley.file.pk)
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            core_models.File.objects.filter(pk=self.galley.file.pk).exists()
        )


class GalleyCreateTests(JatsEditorTestCase):
    def post(self, article=None, **body):
        article = article or self.article
        return self.api("post", "galley/%d/" % article.pk, data=json.dumps(body))

    def test_creates_xml_galley_with_images(self):
        response = self.post(
            jatsXml=NEW_XML,
            images=[
                {"filename": "fig1.png", "data": data_uri(fixture_bytes("fig1.png"))}
            ],
            locale="en",
            publicationId=1,
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        galley = core_models.Galley.objects.get(pk=body["galleyId"])
        self.assertEqual(galley.article, self.article)
        self.assertEqual(galley.type, "xml")
        self.assertEqual(galley.label, "XML")
        self.assertTrue(galley.file.is_galley)
        self.assertEqual(body["fileId"], galley.file.pk)
        self.assertEqual(body["submissionFileId"], galley.file.pk)
        self.assertEqual(files.get_file(galley.file, self.article), NEW_XML)
        self.assertEqual(galley.images.count(), 1)
        self.assertEqual(body["dependentFiles"][0]["status"], "created")
        self.assertEqual(galley.file.owner, self.editor)

    def test_custom_label_and_filename(self):
        response = self.post(jatsXml=NEW_XML, label="JATS", fileName="paper.xml")
        galley = core_models.Galley.objects.get(pk=response.json()["galleyId"])
        self.assertEqual(galley.label, "JATS")
        self.assertEqual(galley.file.original_filename, "paper.xml")

    def test_rejects_published_article(self):
        published = helpers.create_article(
            self.journal,
            stage=submission_models.STAGE_PUBLISHED,
            date_published=timezone.now() - timezone.timedelta(days=1),
        )
        response = self.post(article=published, jatsXml=NEW_XML)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(published.galley_set.count(), 0)

    def test_rejects_malformed_xml(self):
        self.assertEqual(self.post(jatsXml="<article>").status_code, 422)
        self.assertEqual(self.article.galley_set.count(), 1)

    def test_article_of_other_journal_is_not_found(self):
        self.assertEqual(
            self.post(article=self.other_article, jatsXml=NEW_XML).status_code, 404
        )
