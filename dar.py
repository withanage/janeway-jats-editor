"""Builds the Document Archive (DAR) JSON served by ``GET document/<id>/``.

The shape matches the OJS xmlEditor plugin so that pubReady can use the
same loader: a ``resources`` map with ``manifest.xml`` and the unchanged
``manuscript.xml`` as utf8 resources, and every dependent image as a
``url`` resource keyed by its file name."""

import os
from xml.etree import ElementTree

from lxml import etree

MANIFEST_FILE = "manifest.xml"
MANUSCRIPT_FILE = "manuscript.xml"
XLINK_NS = "http://www.w3.org/1999/xlink"

MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "webp": "image/webp",
}


class NotWellFormed(ValueError):
    """The manuscript could not be parsed as XML."""


def secure_parser():
    # No entity expansion, no network, no external DTD: closes the XXE door.
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
        remove_blank_text=False,
    )


def parse(manuscript_xml):
    if isinstance(manuscript_xml, str):
        manuscript_xml = manuscript_xml.encode("utf-8")
    if not manuscript_xml.strip():
        raise NotWellFormed("Manuscript is empty")
    try:
        return etree.fromstring(manuscript_xml, parser=secure_parser())
    except etree.XMLSyntaxError as exc:
        raise NotWellFormed(str(exc)) from exc


def find_figure_assets(root):
    assets = []
    for position, figure in enumerate(root.iter("fig"), start=1):
        graphic = next(figure.iter("graphic"), None)
        if graphic is None:
            continue
        path = graphic.get("{%s}href" % XLINK_NS, "")
        extension = os.path.splitext(path)[1].lstrip(".").lower()
        assets.append(
            {
                "id": figure.get("id") or "fig-%d" % position,
                "type": MIME_TYPES.get(extension, "application/octet-stream"),
                "path": path,
            }
        )
    return assets


def create_manifest(assets):
    root = ElementTree.Element("dar")
    documents = ElementTree.SubElement(root, "documents")
    ElementTree.SubElement(
        documents,
        "document",
        {"id": "manuscript", "type": "article", "path": MANUSCRIPT_FILE},
    )
    container = ElementTree.SubElement(root, "assets")
    for asset in assets:
        ElementTree.SubElement(container, "asset", asset)
    return ElementTree.tostring(root, encoding="unicode")


def text_resource(data):
    return {
        "encoding": "utf8",
        "data": data,
        "size": len(data.encode("utf-8")),
        "createdAt": 0,
        "updatedAt": 0,
    }


def build_dar(manuscript_xml, media_urls):
    """``media_urls`` maps a dependent file name to the URL it can be fetched
    from. Raises :class:`NotWellFormed` when the manuscript does not parse."""
    if isinstance(manuscript_xml, bytes):
        manuscript_xml = manuscript_xml.decode("utf-8")
    manifest = create_manifest(find_figure_assets(parse(manuscript_xml)))

    resources = {
        str(name): {"encoding": "url", "data": url} for name, url in media_urls.items()
    }
    # Archive files last, so a dependent file named like one cannot replace it.
    resources[MANIFEST_FILE] = text_resource(manifest)
    resources[MANUSCRIPT_FILE] = text_resource(manuscript_xml)
    return {"version": 1, "resources": resources}
