"""Journal-scoped API token authentication for the editor API.

The token is generated once in the manager page, shown to the editor
administrator, and only its SHA-256 hash is stored. Clients send it as
``Authorization: Bearer <token>`` or, for servers that strip that header,
as the ``apiToken`` query parameter."""

import functools
import hashlib
import hmac
import secrets

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from plugins.jats_editor import config


def generate_token():
    return secrets.token_urlsafe(32)


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token, journal):
    stored = config.token_hash(journal)
    if not token or not stored:
        return False
    return hmac.compare_digest(hash_token(token), stored)


def token_from_request(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.GET.get("apiToken", "").strip()


def error(status, message):
    return JsonResponse({"error": message}, status=status)


def api_token_required(view):
    """Resolve the journal, check the plugin is enabled there, verify the
    token and attach the service account as ``request.api_account``."""

    @csrf_exempt
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        journal = getattr(request, "journal", None)
        if journal is None:
            return error(404, "This endpoint is only available on a journal.")
        if not config.is_enabled(journal):
            return error(403, "The JATS editor plugin is not enabled for this journal.")
        if not verify_token(token_from_request(request), journal):
            response = error(401, "Missing or invalid API token.")
            response["WWW-Authenticate"] = 'Bearer realm="jats-editor"'
            return response
        account = config.service_account(journal)
        if account is None:
            return error(
                403, "No active service account is configured for the JATS editor."
            )
        request.api_account = account
        return view(request, *args, **kwargs)

    return wrapper
