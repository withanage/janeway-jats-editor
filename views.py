from urllib.parse import urlencode

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render, reverse
from django.views.decorators.http import require_http_methods

from core import files
from core import models as core_models
from plugins.jats_editor import auth, config, forms, logic
from security.decorators import editor_user_required, production_user_or_editor_required

OPEN_PATH = "/janeway/open"


@editor_user_required
@require_http_methods(["GET", "POST"])
def manager(request):
    journal = request.journal
    new_token = None
    form = forms.SettingsForm(journal, initial=forms.SettingsForm.initial_for(journal))

    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "rotate_token":
            new_token = auth.generate_token()
            config.set_value("api_token_hash", auth.hash_token(new_token), journal)
            messages.success(
                request,
                "A new API token was generated. Copy it now; it is not shown again.",
            )
        elif action == "revoke_token":
            config.set_value("api_token_hash", "", journal)
            messages.success(request, "The API token was revoked.")
            return redirect(reverse("jats_editor_manager"))
        else:
            form = forms.SettingsForm(journal, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "JATS editor settings saved.")
                return redirect(reverse("jats_editor_manager"))

    context = {
        "form": form,
        "new_token": new_token,
        "has_token": bool(config.token_hash(journal)),
        "api_root": request.build_absolute_uri(reverse("jats_editor_api_ping")).rsplit(
            "ping/", 1
        )[0],
        "journal": journal,
    }
    return render(request, "jats_editor/manager.html", context)


@production_user_or_editor_required
def galleys(request):
    galley_list = (
        core_models.Galley.objects.filter(
            article__journal=request.journal,
            article__stage__in=logic.DEFAULT_STAGES,
        )
        .select_related("article", "file")
        .order_by("-article__pk", "sequence")
    )
    galley_list = [
        g
        for g in galley_list
        if g.type == "xml" or g.file.mime_type in files.XML_MIMETYPES
    ]
    context = {
        "galleys": galley_list,
        "editor_url": config.editor_base_url(request.journal),
        "enabled": config.is_enabled(request.journal),
    }
    return render(request, "jats_editor/galleys.html", context)


def editor_open_url(journal, article, **extra):
    base = config.editor_base_url(journal)
    if not base:
        return None
    params = {
        "host": journal.site_url(),
        "journal": journal.code,
        "article": article.pk,
    }
    params.update(extra)
    return base + OPEN_PATH + "?" + urlencode(params)


def _redirect_to_editor(request, article, **extra):
    url = editor_open_url(request.journal, article, **extra)
    if url is None:
        messages.error(request, "Set the pubReady editor URL before opening documents.")
        return redirect(reverse("jats_editor_manager"))
    return redirect(url)


@production_user_or_editor_required
def open_galley(request, article_id, galley_id):
    article = logic.get_article(request.journal, article_id)
    galley = logic.get_galley(request.journal, galley_id)
    if galley.article_id != article.pk:
        raise Http404("Galley not found")
    return _redirect_to_editor(request, article, galley=galley.pk)


@production_user_or_editor_required
def open_file(request, article_id, file_id):
    article = logic.get_article(request.journal, article_id)
    file_obj = logic.get_article_file(article, file_id)
    return _redirect_to_editor(request, article, file=file_obj.pk)
