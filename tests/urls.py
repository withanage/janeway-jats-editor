"""URLconf used by the plugin's tests.

Janeway mounts plugin URLs only for plugins that are enabled in the database
at the time core.include_urls is imported, which never holds for a fresh test
database. This URLconf mounts the plugin under the same prefix Janeway would
use in production.
"""

from django.urls import include, re_path

from core.urls import urlpatterns as core_urlpatterns

urlpatterns = [
    re_path(r"^plugins/jats-editor/", include("plugins.jats_editor.urls")),
] + core_urlpatterns
