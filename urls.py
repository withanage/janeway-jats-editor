from django.urls import re_path

from plugins.jats_editor import api_views, views

API = r"^api/v1/"

urlpatterns = [
    re_path(r"^manager/$", views.manager, name="jats_editor_manager"),
    re_path(r"^galleys/$", views.galleys, name="jats_editor_galleys"),
    re_path(
        r"^open/(?P<article_id>\d+)/galley/(?P<galley_id>\d+)/$",
        views.open_galley,
        name="jats_editor_open_galley",
    ),
    re_path(
        r"^open/(?P<article_id>\d+)/file/(?P<file_id>\d+)/$",
        views.open_file,
        name="jats_editor_open_file",
    ),
    re_path(API + r"ping/$", api_views.ping, name="jats_editor_api_ping"),
    re_path(
        API + r"journal-metadata/$",
        api_views.journal_metadata,
        name="jats_editor_api_journal_metadata",
    ),
    re_path(API + r"articles/$", api_views.articles, name="jats_editor_api_articles"),
    re_path(
        API + r"article/(?P<article_id>\d+)/$",
        api_views.article,
        name="jats_editor_api_article",
    ),
    re_path(
        API + r"workflow-files/(?P<article_id>\d+)/$",
        api_views.workflow_files,
        name="jats_editor_api_workflow_files",
    ),
    re_path(
        API + r"workflow-files/(?P<article_id>\d+)/(?P<file_id>\d+)/download/$",
        api_views.workflow_file_download,
        name="jats_editor_api_workflow_file_download",
    ),
    re_path(
        API + r"document/(?P<galley_id>\d+)/$",
        api_views.document,
        name="jats_editor_api_document",
    ),
    re_path(
        API + r"media/(?P<galley_id>\d+)/$",
        api_views.media_collection,
        name="jats_editor_api_media",
    ),
    re_path(
        API + r"media/(?P<galley_id>\d+)/(?P<file_id>\d+)/$",
        api_views.media_file,
        name="jats_editor_api_media_file",
    ),
    re_path(
        API + r"galley/(?P<article_id>\d+)/$",
        api_views.galley,
        name="jats_editor_api_galley",
    ),
]
