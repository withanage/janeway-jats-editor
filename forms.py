from django import forms

from core import models as core_models
from plugins.jats_editor import config

SERVICE_ROLES = ("editor", "production", "typesetter", "journal-manager")


def service_account_choices(journal):
    return (
        core_models.Account.objects.filter(
            is_active=True,
            accountrole__journal=journal,
            accountrole__role__slug__in=SERVICE_ROLES,
        )
        .distinct()
        .order_by("last_name", "first_name", "email")
    )


class AccountChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, account):
        return "%s (%s)" % (account.full_name(), account.email)


class SettingsForm(forms.Form):
    enabled = forms.BooleanField(
        required=False,
        label="Enable the JATS editor API for this journal",
    )
    editor_base_url = forms.URLField(
        required=False,
        label="pubReady editor URL",
        help_text="Base URL of the pubReady installation, e.g. https://editor.example.org",
    )
    max_upload_mb = forms.IntegerField(
        min_value=1,
        max_value=1024,
        label="Maximum upload size (MB)",
    )
    api_account = AccountChoiceField(
        queryset=core_models.Account.objects.none(),
        required=True,
        label="Service account",
        help_text="Files written through the API are owned by this account.",
    )

    def __init__(self, journal, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal = journal
        self.fields["api_account"].queryset = service_account_choices(journal)

    @classmethod
    def initial_for(cls, journal):
        account = config.service_account(journal)
        return {
            "enabled": config.is_enabled(journal),
            "editor_base_url": config.editor_base_url(journal),
            "max_upload_mb": config.max_upload_bytes(journal) // (1024 * 1024),
            "api_account": account.pk if account else None,
        }

    def save(self):
        data = self.cleaned_data
        config.set_value(
            "jats_editor_enabled", "on" if data["enabled"] else "", self.journal
        )
        config.set_value(
            "editor_base_url", data["editor_base_url"].rstrip("/"), self.journal
        )
        config.set_value("max_upload_mb", str(data["max_upload_mb"]), self.journal)
        config.set_value("api_account_id", str(data["api_account"].pk), self.journal)
