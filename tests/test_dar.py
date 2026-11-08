from xml.etree import ElementTree

from django.test import SimpleTestCase

from plugins.jats_editor import dar
from plugins.jats_editor.tests.base import fixture_bytes


class BuildDarTests(SimpleTestCase):
    def setUp(self):
        self.xml = fixture_bytes("article.xml").decode("utf-8")

    def test_returns_manuscript_unchanged(self):
        result = dar.build_dar(self.xml, {})
        manuscript = result["resources"]["manuscript.xml"]
        self.assertEqual(result["version"], 1)
        self.assertEqual(manuscript["encoding"], "utf8")
        self.assertEqual(manuscript["data"], self.xml)
        self.assertEqual(manuscript["size"], len(self.xml.encode("utf-8")))

    def test_manifest_lists_figure_graphics(self):
        result = dar.build_dar(self.xml, {})
        manifest = ElementTree.fromstring(result["resources"]["manifest.xml"]["data"])
        document = manifest.find("documents/document")
        self.assertEqual(document.get("path"), "manuscript.xml")
        assets = manifest.findall("assets/asset")
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].get("id"), "f1")
        self.assertEqual(assets[0].get("path"), "fig1.png")
        self.assertEqual(assets[0].get("type"), "image/png")

    def test_figure_without_id_gets_positional_id(self):
        xml = (
            '<article xmlns:xlink="http://www.w3.org/1999/xlink"><body>'
            '<fig><graphic xlink:href="a.jpg"/></fig>'
            '<fig><graphic xlink:href="b.unknown"/></fig>'
            "</body></article>"
        )
        manifest = ElementTree.fromstring(
            dar.build_dar(xml, {})["resources"]["manifest.xml"]["data"]
        )
        assets = manifest.findall("assets/asset")
        self.assertEqual([a.get("id") for a in assets], ["fig-1", "fig-2"])
        self.assertEqual(assets[0].get("type"), "image/jpeg")
        self.assertEqual(assets[1].get("type"), "application/octet-stream")

    def test_media_urls_become_url_resources(self):
        result = dar.build_dar(self.xml, {"fig1.png": "https://j.example/media/1/"})
        self.assertEqual(
            result["resources"]["fig1.png"],
            {"encoding": "url", "data": "https://j.example/media/1/"},
        )

    def test_media_cannot_shadow_archive_files(self):
        result = dar.build_dar(self.xml, {"manuscript.xml": "https://evil.example/"})
        self.assertEqual(result["resources"]["manuscript.xml"]["data"], self.xml)

    def test_rejects_malformed_xml(self):
        with self.assertRaises(dar.NotWellFormed):
            dar.build_dar("<article><body></article>", {})

    def test_rejects_empty_document(self):
        with self.assertRaises(dar.NotWellFormed):
            dar.build_dar("", {})

    def test_does_not_expand_external_entities(self):
        xml = (
            '<?xml version="1.0"?><!DOCTYPE article [<!ENTITY xxe SYSTEM "file:///etc/hostname">]>'
            '<article xmlns:xlink="http://www.w3.org/1999/xlink"><body>'
            '<fig id="f1"><label>&xxe;</label><graphic xlink:href="fig1.png"/></fig>'
            "</body></article>"
        )
        with open("/etc/hostname") as fh:
            secret = fh.read().strip()
        result = dar.build_dar(xml, {})
        manifest = result["resources"]["manifest.xml"]["data"]
        self.assertTrue(secret)
        self.assertNotIn(secret, manifest)
        self.assertEqual(result["resources"]["manuscript.xml"]["data"], xml)

    def test_rejects_external_entity_in_attribute(self):
        xml = (
            '<?xml version="1.0"?><!DOCTYPE article [<!ENTITY xxe SYSTEM "file:///etc/hostname">]>'
            '<article xmlns:xlink="http://www.w3.org/1999/xlink"><body>'
            '<fig id="f1"><graphic xlink:href="&xxe;"/></fig></body></article>'
        )
        with self.assertRaises(dar.NotWellFormed):
            dar.build_dar(xml, {})
