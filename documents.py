"""Request payload validation and the file write path for the document,
media and galley endpoints. Validation happens fully before anything is
written so a bad image never leaves a half-saved manuscript behind."""

import base64
import json
import os
import re

import magic
from django.core.exceptions import RequestDataTooBig
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from core import files
from core import models as core_models
from plugins.jats_editor import config, dar

DATA_URI = re.compile(r"^data:[^;,]*(;[^;,]*)*;base64,", re.IGNORECASE)
IMAGE_LABEL = "Galley Image"
DEFAULT_GALLEY_LABEL = "XML"
DEFAULT_GALLEY_FILENAME = "article.xml"


class PayloadError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def parse_json(request):
    try:
        raw = request.body
    except RequestDataTooBig as exc:
        raise PayloadError(413, "Request body is too large.") from exc
    if not raw:
        raise PayloadError(400, "Request body is empty.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise PayloadError(400, "Request body is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise PayloadError(400, "Request body must be a JSON object.")
    return payload


def manuscript_from_payload(payload):
    text = payload.get("jatsXml")
    if not text:
        resources = payload.get("resources") or {}
        text = (resources.get(dar.MANUSCRIPT_FILE) or {}).get("data")
    if not isinstance(text, str) or not text.strip():
        raise PayloadError(400, "Missing required field: jatsXml")
    return text


def safe_basename(name):
    """Reduce a client supplied name to a plain file name. Rejects names
    that would be empty or refer to the current or parent directory."""
    if not isinstance(name, str):
        raise PayloadError(400, "File name must be a string.")
    cleaned = os.path.basename(name.replace("\\", "/")).strip()
    cleaned = cleaned.replace("\x00", "")
    if cleaned in ("", ".", ".."):
        raise PayloadError(400, "File name is missing or invalid.")
    return cleaned


def decode_data(data):
    if not isinstance(data, str) or not data.strip():
        raise PayloadError(400, "File data is missing.")
    data = DATA_URI.sub("", data.strip())
    try:
        return base64.b64decode(data, validate=True)
    except (ValueError, TypeError) as exc:
        raise PayloadError(400, "File data is not valid base64.") from exc


def check_size(blob, journal, what="File"):
    limit = config.max_upload_bytes(journal)
    if len(blob) > limit:
        raise PayloadError(
            413, "%s exceeds the upload limit of %d bytes." % (what, limit)
        )


def check_image(blob, filename):
    detected = magic.from_buffer(blob, mime=True)
    if detected not in files.IMAGE_MIMETYPES:
        raise PayloadError(
            415, "%s is not a supported image type (%s)." % (filename, detected)
        )
    return detected


def validated_manuscript(payload, journal):
    """Returns the manuscript text after size and well-formedness checks."""
    text = manuscript_from_payload(payload)
    check_size(text.encode("utf-8"), journal, "Manuscript")
    try:
        dar.parse(text)
    except dar.NotWellFormed as exc:
        raise PayloadError(422, "Manuscript is not well-formed XML: %s" % exc) from exc
    return text


def validated_image(entry, journal):
    """Normalises one image entry to ``(filename, bytes, mime)``."""
    if not isinstance(entry, dict):
        raise PayloadError(400, "Each image must be an object.")
    filename = safe_basename(entry.get("filename") or entry.get("fileName") or "")
    blob = decode_data(entry.get("data"))
    check_size(blob, journal, filename)
    mime = check_image(blob, filename)
    return filename, blob, mime


def validated_images(payload, journal):
    images = payload.get("images") or []
    if not isinstance(images, list):
        raise PayloadError(400, "images must be a list.")
    return [validated_image(entry, journal) for entry in images]


def is_xml_galley(galley):
    return galley.type == "xml" or galley.file.mime_type in files.XML_MIMETYPES


def _upload(filename, blob, mime):
    return SimpleUploadedFile(filename, blob, mime)


def overwrite(file_obj, filename, blob, mime, account):
    article_path = ("articles", file_obj.article_id)
    files.overwrite_file(
        _upload(filename, blob, mime), file_obj, path_parts=article_path
    )
    file_obj.owner = account
    file_obj.save()
    return file_obj


def write_manuscript(galley, text, account):
    filename = galley.file.original_filename or DEFAULT_GALLEY_FILENAME
    if not filename.lower().endswith(".xml"):
        filename = os.path.splitext(filename)[0] + ".xml"
    return overwrite(
        galley.file, filename, text.encode("utf-8"), "application/xml", account
    )


def upsert_image(galley, filename, blob, mime, account):
    existing = galley.images.filter(original_filename=filename).order_by("pk").first()
    if existing is not None:
        overwrite(existing, filename, blob, mime, account)
        return existing, "updated"
    image = files.save_file_to_article(
        _upload(filename, blob, mime), galley.article, account, label=IMAGE_LABEL
    )
    galley.images.add(image)
    return image, "created"


def dependent_entry(image, status):
    return {
        "filename": image.original_filename,
        "submissionFileId": image.pk,
        "fileId": image.pk,
        "status": status,
    }


@transaction.atomic
def save_document(galley, text, images, account):
    write_manuscript(galley, text, account)
    dependent = [
        dependent_entry(*upsert_image(galley, name, blob, mime, account))
        for name, blob, mime in images
    ]
    return {
        "success": True,
        "galleyId": galley.pk,
        "fileId": galley.file_id,
        "submissionFileId": galley.file_id,
        "dependentFiles": dependent,
        "historyCount": galley.file.history.count(),
    }


@transaction.atomic
def create_galley(article, text, images, account, label, filename):
    file_obj = files.save_file_to_article(
        _upload(filename, text.encode("utf-8"), "application/xml"),
        article,
        account,
        label=label,
        is_galley=True,
    )
    sequence = article.galley_set.count()
    galley = core_models.Galley.objects.create(
        article=article, file=file_obj, label=label, type="xml", sequence=sequence
    )
    dependent = [
        dependent_entry(*upsert_image(galley, name, blob, mime, account))
        for name, blob, mime in images
    ]
    return {
        "success": True,
        "galleyId": galley.pk,
        "fileId": file_obj.pk,
        "submissionFileId": file_obj.pk,
        "dependentFiles": dependent,
    }


def galley_filename(payload):
    name = payload.get("fileName") or payload.get("filename") or DEFAULT_GALLEY_FILENAME
    name = safe_basename(name)
    if not name.lower().endswith(".xml"):
        name += ".xml"
    return name


def media_entry(payload):
    """``{media:{fileName,data}}`` or the same keys at the top level."""
    entry = payload.get("media") if isinstance(payload.get("media"), dict) else payload
    return {
        "filename": entry.get("fileName") or entry.get("filename"),
        "data": entry.get("data") or entry.get("content"),
    }
