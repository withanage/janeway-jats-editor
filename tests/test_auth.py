from plugins.jats_editor.tests.base import TOKEN, JatsEditorTestCase


class PingAuthTests(JatsEditorTestCase):
    def test_rejects_request_without_token(self):
        response = self.api("get", "ping/", token=None)
        self.assertEqual(response.status_code, 401)

    def test_rejects_wrong_token(self):
        response = self.api("get", "ping/", token="wrong-" + TOKEN)
        self.assertEqual(response.status_code, 401)

    def test_accepts_bearer_header(self):
        response = self.api("get", "ping/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["application"], "janeway")
        self.assertEqual(response.json()["journal"]["code"], self.journal.code)

    def test_accepts_api_token_query_parameter(self):
        response = self.api("get", "ping/", via="query")
        self.assertEqual(response.status_code, 200)

    def test_rejects_when_journal_setting_disabled(self):
        self.set_setting("jats_editor_enabled", "")
        response = self.api("get", "ping/")
        self.assertEqual(response.status_code, 403)

    def test_rejects_when_plugin_disabled(self):
        self.plugin.enabled = False
        self.plugin.save()
        response = self.api("get", "ping/")
        self.assertEqual(response.status_code, 403)

    def test_token_is_journal_scoped(self):
        self.set_setting("jats_editor_enabled", "on", journal=self.other_journal)
        response = self.api("get", "ping/", SERVER_NAME=self.other_journal.domain)
        self.assertEqual(response.status_code, 401)

    def test_rejects_when_no_service_account(self):
        self.set_setting("api_account_id", "")
        response = self.api("get", "ping/")
        self.assertEqual(response.status_code, 403)
