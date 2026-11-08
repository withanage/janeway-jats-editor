"""Template hooks registered in ``plugin_settings.hook_registry``. Each
returns an HTML string or "" and must never raise: Janeway swallows hook
errors but logs them on every page render."""

from django.shortcuts import reverse
from django.utils.html import format_html

from core import files
from plugins.jats_editor import config


def _journal(context):
    request = context.get("request")
    return getattr(request, "journal", None)


def conversion_row(context, file_obj, article, *args, **kwargs):
    """Adds an "Open in JATS editor" row to the typesetting transform
    dialog for XML manuscript files."""
    journal = _journal(context)
    if journal is None or not config.is_enabled(journal):
        return ""
    if file_obj.mime_type not in files.XML_MIMETYPES:
        return ""
    url = reverse(
        "jats_editor_open_file",
        kwargs={"article_id": article.pk, "file_id": file_obj.pk},
    )
    return format_html(
        "<tr><td>pubReady</td>"
        "<td>Open this JATS XML in the pubReady editor and save it back as an XML galley.</td>"
        '<td><a class="button small" href="{}">Open in editor</a></td></tr>',
        url,
    )


def editor_nav_block(context, *args, **kwargs):
    journal = _journal(context)
    if journal is None or not config.is_enabled(journal):
        return ""
    return format_html(
        '<li><a href="{}"><i class="fa fa-code">&nbsp;</i> JATS Editor</a></li>',
        reverse("jats_editor_galleys"),
    )
