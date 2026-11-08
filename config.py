"""Typed access to the per-journal plugin settings.

Named ``config`` rather than ``settings`` so it is never confused with
``django.conf.settings`` inside the plugin."""

from core import models as core_models
from plugins.jats_editor import plugin_settings
from utils import setting_handler

DEFAULT_MAX_UPLOAD_MB = 25


def plugin_row():
    return plugin_settings.JatsEditorPlugin.get_self()


def _raw(name, journal):
    plugin = plugin_row()
    if plugin is None:
        return ""
    setting = setting_handler.get_plugin_setting(plugin, name, journal)
    if setting is None or setting.value is None:
        return ""
    return str(setting.value)


def set_value(name, value, journal):
    setting_handler.save_plugin_setting(plugin_row(), name, value, journal)


def is_enabled(journal):
    plugin = plugin_row()
    if plugin is None or not plugin.enabled:
        return False
    return _raw("jats_editor_enabled", journal) == "on"


def token_hash(journal):
    return _raw("api_token_hash", journal).strip()


def editor_base_url(journal):
    return _raw("editor_base_url", journal).strip().rstrip("/")


def max_upload_bytes(journal):
    raw = _raw("max_upload_mb", journal).strip()
    try:
        megabytes = int(raw) if raw else DEFAULT_MAX_UPLOAD_MB
    except ValueError:
        megabytes = DEFAULT_MAX_UPLOAD_MB
    if megabytes <= 0:
        megabytes = DEFAULT_MAX_UPLOAD_MB
    return megabytes * 1024 * 1024


def service_account(journal):
    """The account that owns files written through the API, or None."""
    raw = _raw("api_account_id", journal).strip()
    if not raw.isdigit():
        return None
    return core_models.Account.objects.filter(pk=int(raw), is_active=True).first()
