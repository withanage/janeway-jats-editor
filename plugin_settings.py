from utils import plugins
from utils.install import update_settings

PLUGIN_NAME = "JATS Editor Plugin"
DISPLAY_NAME = "JATS Editor"
DESCRIPTION = (
    "Exposes an API so that the pubReady JATS XML editor can open, edit and "
    "save XML galleys and their figures."
)
AUTHOR = "Dulip Withanage"
VERSION = "0.1.0"
SHORT_NAME = "jats_editor"
MANAGER_URL = "jats_editor_manager"
JANEWAY_VERSION = "1.8.0"
IS_WORKFLOW_PLUGIN = False


class JatsEditorPlugin(plugins.Plugin):
    plugin_name = PLUGIN_NAME
    display_name = DISPLAY_NAME
    description = DESCRIPTION
    author = AUTHOR
    short_name = SHORT_NAME
    manager_url = MANAGER_URL
    version = VERSION
    janeway_version = JANEWAY_VERSION
    is_workflow_plugin = IS_WORKFLOW_PLUGIN


def install():
    JatsEditorPlugin.install()
    update_settings(file_path="plugins/jats_editor/install/settings.json")


def hook_registry():
    return {
        "conversion_row": {
            "module": "plugins.jats_editor.hooks",
            "function": "conversion_row",
        },
        "journal_editor_nav_block": {
            "module": "plugins.jats_editor.hooks",
            "function": "editor_nav_block",
        },
    }
