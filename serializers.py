"""Plain-dict serializers. Keys follow the OJS xmlEditor plugin where a
counterpart exists so that pubReady's existing client code applies."""

from django.conf import settings

from plugins.jats_editor import logic
from utils import setting_handler


def _setting(journal, group, name):
    try:
        return setting_handler.get_setting(group, name, journal, create=False).value
    except Exception:  # noqa: BLE001 - missing settings differ per install
        return None


def _iso(value):
    return value.isoformat() if value else None


def journal_metadata(journal):
    locale = (
        _setting(journal, "general", "default_journal_language")
        or settings.LANGUAGE_CODE
    )
    url = journal.site_url()
    name = journal.name
    description = _setting(journal, "general", "journal_description")
    publisher = journal.publisher or (journal.press.name if journal.press else None)
    return {
        "id": journal.pk,
        "urlPath": journal.code,
        "slug": journal.code,
        "name": name,
        "names": {locale: name},
        "abbreviation": journal.code,
        "abbreviations": {locale: journal.code},
        "description": description,
        "descriptions": {locale: description},
        "primaryLocale": locale,
        "supportedLocales": [locale],
        "onlineIssn": journal.issn,
        "printIssn": journal.print_issn,
        "publisherInstitution": publisher,
        "publisherUrl": _setting(journal, "general", "publisher_url"),
        "contactEmail": _setting(journal, "general", "main_contact"),
        "copyrightNotice": {locale: _setting(journal, "general", "copyright_notice")},
        "doiPrefix": _setting(journal, "Identifiers", "crossref_prefix"),
        "journalDoi": journal.doi,
        "domain": journal.domain,
        "janewayUrl": url,
        "ojsUrl": url,
        "janewayArticlesUrl": journal.site_url(path="/articles/"),
        "janewaySettingsUrl": journal.site_url(path="/manager/settings/"),
        "press": {"name": journal.press.name if journal.press else None},
    }


def author(frozen):
    return {
        "id": frozen.pk,
        "givenName": frozen.first_name,
        "familyName": frozen.last_name,
        "fullName": frozen.full_name(),
        "email": frozen.email,
        "orcid": frozen.orcid,
        "affiliation": str(frozen.affiliation() or ""),
        "order": frozen.order,
    }


def galley_file(file_obj):
    return {
        "id": file_obj.pk,
        "fileId": file_obj.pk,
        "name": file_obj.original_filename,
        "mimetype": file_obj.mime_type,
        "label": file_obj.label,
        "uploadedAt": _iso(file_obj.date_uploaded),
        "updatedAt": _iso(file_obj.last_modified),
    }


def galley(galley_obj):
    return {
        "id": galley_obj.pk,
        "label": galley_obj.label,
        "type": galley_obj.type,
        "fileId": galley_obj.file_id,
        "fileName": galley_obj.file.original_filename,
        "mimeType": galley_obj.file.mime_type,
        "public": galley_obj.public,
        "sequence": galley_obj.sequence,
        "images": [galley_file(image) for image in galley_obj.images.all()],
    }


def article_summary(article):
    return {
        "id": article.pk,
        "title": article.title,
        "stage": article.stage,
        "stageName": article.get_stage_display()
        if hasattr(article, "get_stage_display")
        else article.stage,
        "datePublished": _iso(article.date_published),
        "dateSubmitted": _iso(article.date_submitted),
        "section": article.section.name if article.section else None,
        "authors": [author(a) for a in article.frozen_authors().order_by("order")],
        "doi": article.get_doi(),
        "language": article.language,
        "galleyCount": article.galley_set.count(),
        "isPublished": article.is_published,
        "url": article.url,
    }


def article_detail(article):
    data = article_summary(article)
    issue = article.primary_issue
    data.update(
        {
            "abstract": article.abstract,
            "keywords": [k.word for k in article.keywords.all()],
            "license": (
                {"name": article.license.name, "url": article.license.url}
                if article.license
                else None
            ),
            "issue": (
                {
                    "id": issue.pk,
                    "title": issue.display_title,
                    "volume": issue.volume,
                    "number": issue.issue,
                }
                if issue
                else None
            ),
            "firstPage": article.first_page,
            "pageNumbers": article.page_numbers,
            "galleys": [
                galley(g) for g in article.galley_set.all().order_by("sequence", "pk")
            ],
        }
    )
    return data


def workflow_file(file_obj, file_stage, stage_name, parent=None, galley_id=None):
    data = galley_file(file_obj)
    data.update(
        {
            "fileStage": file_stage,
            "workflowStageName": stage_name,
            "isDependent": parent is not None,
            "parentFileId": parent.pk if parent else None,
            "galleyId": galley_id,
        }
    )
    return data


def workflow_files(article, stages):
    entries = []
    if logic.WORKFLOW_STAGE_COPYEDITING in stages:
        for file_obj in article.manuscript_files.all().order_by("pk"):
            entries.append(
                workflow_file(file_obj, logic.FILE_STAGE_COPYEDIT, "Copyediting")
            )
    if logic.WORKFLOW_STAGE_PRODUCTION in stages:
        for galley_obj in article.galley_set.all().order_by("sequence", "pk"):
            entries.append(
                workflow_file(
                    galley_obj.file,
                    logic.FILE_STAGE_PRODUCTION,
                    "Production",
                    galley_id=galley_obj.pk,
                )
            )
            for image in galley_obj.images.all().order_by("pk"):
                entries.append(
                    workflow_file(
                        image,
                        logic.FILE_STAGE_DEPENDENT,
                        "Production",
                        parent=galley_obj.file,
                        galley_id=galley_obj.pk,
                    )
                )
    return entries
