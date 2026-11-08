"""Query helpers shared by the API views. Everything here is scoped to the
journal on the request so a token can never reach another journal's data."""

from django.http import Http404

from core import models as core_models
from submission import models as submission_models

# OJS file-stage numbers kept so pubReady can reuse its OJS file browser.
FILE_STAGE_COPYEDIT = 9
FILE_STAGE_PRODUCTION = 10
FILE_STAGE_DEPENDENT = 17
WORKFLOW_STAGE_COPYEDITING = 4
WORKFLOW_STAGE_PRODUCTION = 5

DEFAULT_STAGES = (
    submission_models.STAGE_TYPESETTING,
    submission_models.STAGE_TYPESETTING_PLUGIN,
    submission_models.STAGE_PROOFING,
    submission_models.STAGE_READY_FOR_PUBLICATION,
    submission_models.STAGE_PUBLISHED,
)


def journal_articles(journal):
    return submission_models.Article.objects.filter(journal=journal)


def get_article(journal, article_id):
    article = journal_articles(journal).filter(pk=article_id).first()
    if article is None:
        raise Http404("Article not found")
    return article


def get_galley(journal, galley_id):
    galley = (
        core_models.Galley.objects.filter(pk=galley_id, article__journal=journal)
        .select_related("article", "file")
        .first()
    )
    if galley is None:
        raise Http404("Galley not found")
    return galley


def get_article_file(article, file_id):
    """A file is reachable only if it is one of the article's manuscript
    files, data files, galley files or galley images."""
    candidates = core_models.File.objects.filter(pk=file_id, article_id=article.pk)
    file_obj = candidates.first()
    if file_obj is None:
        raise Http404("File not found")
    allowed = (
        article.manuscript_files.filter(pk=file_obj.pk).exists()
        or article.data_figure_files.filter(pk=file_obj.pk).exists()
        or article.galley_set.filter(file=file_obj).exists()
        or article.galley_set.filter(images=file_obj).exists()
    )
    if not allowed:
        raise Http404("File not found")
    return file_obj


def galley_image(galley, file_id):
    image = galley.images.filter(pk=file_id).first()
    if image is None:
        raise Http404("Image not found")
    return image


def parse_stage_filter(raw):
    """``?stages=4,5`` → set of workflow stage numbers; empty → both."""
    if not raw:
        return {WORKFLOW_STAGE_COPYEDITING, WORKFLOW_STAGE_PRODUCTION}
    stages = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            stages.add(int(part))
    return stages
