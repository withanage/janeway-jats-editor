from urllib.parse import urlencode

from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from core import files
from plugins.jats_editor import (
    auth,
    dar,
    documents,
    logic,
    plugin_settings,
    serializers,
)
from plugins.jats_editor.auth import api_token_required, error

MAX_PAGE = 200


@require_GET
@api_token_required
def ping(request):
    return JsonResponse(
        {
            "application": "janeway",
            "plugin": plugin_settings.SHORT_NAME,
            "version": plugin_settings.VERSION,
            "journal": {"code": request.journal.code, "name": request.journal.name},
        }
    )


@require_GET
@api_token_required
def journal_metadata(request):
    return JsonResponse(
        {"success": True, "metadata": serializers.journal_metadata(request.journal)}
    )


def _int_param(request, name, default):
    raw = request.GET.get(name)
    if raw is None or raw == "":
        return default
    if not raw.isdigit():
        raise ValueError(name)
    return int(raw)


@require_GET
@api_token_required
def articles(request):
    try:
        limit = min(_int_param(request, "limit", 50), MAX_PAGE)
        offset = _int_param(request, "offset", 0)
    except ValueError as exc:
        return error(400, "Parameter %s must be a non-negative integer." % exc)
    stages = [s.strip() for s in request.GET.get("stages", "").split(",") if s.strip()]
    queryset = logic.journal_articles(request.journal).filter(
        stage__in=stages or logic.DEFAULT_STAGES
    )
    queryset = queryset.order_by("-date_published", "-pk")
    items = [serializers.article_summary(a) for a in queryset[offset : offset + limit]]
    return JsonResponse({"itemsMax": queryset.count(), "items": items})


@require_GET
@api_token_required
def article(request, article_id):
    article_obj = logic.get_article(request.journal, article_id)
    return JsonResponse(serializers.article_detail(article_obj))


@require_GET
@api_token_required
def workflow_files(request, article_id):
    article_obj = logic.get_article(request.journal, article_id)
    stages = logic.parse_stage_filter(request.GET.get("stages", ""))
    return JsonResponse(
        {
            "success": True,
            "submissionId": article_obj.pk,
            "files": serializers.workflow_files(article_obj, stages),
        }
    )


@require_GET
@api_token_required
def workflow_file_download(request, article_id, file_id):
    article_obj = logic.get_article(request.journal, article_id)
    file_obj = logic.get_article_file(article_obj, file_id)
    return files.serve_file(request, file_obj, article_obj)


def _payload_error(exc):
    return error(exc.status, exc.message)


def _media_url(request, galley, image):
    url = reverse(
        "jats_editor_api_media_file",
        kwargs={"galley_id": galley.pk, "file_id": image.pk},
    )
    token = auth.token_from_request(request)
    return request.build_absolute_uri(url) + "?" + urlencode({"apiToken": token})


def _document_get(request, galley):
    content = files.get_file(galley.file, galley.article, as_bytes=True)
    if content == "":
        return error(404, "The galley file is missing from disk.")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return error(422, "The galley file is not UTF-8 encoded XML.")
    media = {
        image.original_filename: _media_url(request, galley, image)
        for image in galley.images.all().order_by("pk")
    }
    try:
        return JsonResponse(dar.build_dar(text, media))
    except dar.NotWellFormed as exc:
        return error(422, "The galley is not well-formed XML: %s" % exc)


def _document_put(request, galley):
    try:
        payload = documents.parse_json(request)
        text = documents.validated_manuscript(payload, request.journal)
        images = documents.validated_images(payload, request.journal)
    except documents.PayloadError as exc:
        return _payload_error(exc)
    result = documents.save_document(galley, text, images, request.api_account)
    return JsonResponse(result)


@require_http_methods(["GET", "PUT"])
@api_token_required
def document(request, galley_id):
    galley = logic.get_galley(request.journal, galley_id)
    if not documents.is_xml_galley(galley):
        return error(415, "Only XML galleys can be opened in the editor.")
    if request.method == "PUT":
        return _document_put(request, galley)
    return _document_get(request, galley)


@require_http_methods(["POST"])
@api_token_required
def media_collection(request, galley_id):
    galley = logic.get_galley(request.journal, galley_id)
    try:
        payload = documents.parse_json(request)
        name, blob, mime = documents.validated_image(
            documents.media_entry(payload), request.journal
        )
    except documents.PayloadError as exc:
        return _payload_error(exc)
    image, status = documents.upsert_image(
        galley, name, blob, mime, request.api_account
    )
    body = {
        "success": True,
        "status": status,
        "submissionFileId": image.pk,
        "fileId": image.pk,
    }
    return JsonResponse(body, status=201 if status == "created" else 200)


@require_http_methods(["GET", "DELETE"])
@api_token_required
def media_file(request, galley_id, file_id):
    galley = logic.get_galley(request.journal, galley_id)
    image = logic.galley_image(galley, file_id)
    if request.method == "DELETE":
        galley.images.remove(image)
        image.delete()
        return JsonResponse({"success": True, "deleted": int(file_id)})
    return files.serve_file(request, image, galley.article)


@require_http_methods(["POST"])
@api_token_required
def galley(request, article_id):
    article_obj = logic.get_article(request.journal, article_id)
    if article_obj.is_published:
        return error(400, "Galleys of published articles must be edited, not created.")
    try:
        payload = documents.parse_json(request)
        text = documents.validated_manuscript(payload, request.journal)
        images = documents.validated_images(payload, request.journal)
        filename = documents.galley_filename(payload)
        label = str(payload.get("label") or documents.DEFAULT_GALLEY_LABEL)[:400]
    except documents.PayloadError as exc:
        return _payload_error(exc)
    result = documents.create_galley(
        article_obj, text, images, request.api_account, label, filename
    )
    return JsonResponse(result, status=201)
