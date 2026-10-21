"""
Tests for the final reports of the translation sync commands.
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from openedx_wikilearn_features.meta_translations.management.commands import (
    sync_translated_strings_to_edx_from_meta as fetch_command,
    sync_untranslated_strings_to_meta_from_edx as send_command,
)


class SendCommandReportTest(SimpleTestCase):
    def setUp(self):
        self.command = send_command.Command()
        self.command._RESULT = {
            "updated_blocks_count": 3,
            "success_updated_pages_count": 1,
            "failed_pages": [],
        }

    def test_get_failed_titles(self):
        titles = ["course/en/block1", "course/en/block2", "course/en/block3"]
        responses = [{"result": "Success"}, None, {"result": "error"}]
        self.assertEqual(
            self.command._get_failed_titles(titles, responses),
            ["course/en/block2", "course/en/block3"],
        )

    def test_report_lists_failed_pages(self):
        self.command._RESULT["failed_pages"] = ["course/en/block2"]
        with self.assertLogs(send_command.log, level="INFO") as logs:
            self.command._log_final_report()
        self.assertTrue(any(
            record.levelname == "ERROR" and "failed to update: 1" in record.getMessage()
            and "course/en/block2" in record.getMessage()
            for record in logs.records
        ))

    def test_report_without_failures(self):
        with self.assertLogs(send_command.log, level="INFO") as logs:
            self.command._log_final_report()
        self.assertIn("Total blocks failed to update: 0", [record.getMessage() for record in logs.records])
        self.assertFalse(any(record.levelname == "ERROR" for record in logs.records))


class FetchCommandReportTest(SimpleTestCase):
    def setUp(self):
        self.command = fetch_command.Command()
        self.command._UPDATED_TRANSLATIONS = []
        self.command._UPDATED_BLOCKS = set()
        self.command._TOTAL_REQUESTS = 0
        self.command._FAILED_REQUESTS = 0

    def _result(self, message):
        return {"target_block_id": "block", "message": message}

    def test_report_summarises_results(self):
        self.command._UPDATED_TRANSLATIONS = [
            self._result(fetch_command.UPDATED),
            self._result(fetch_command.UPDATED),
            self._result(fetch_command.UNCHANGED),
            self._result(fetch_command.NOT_TRANSLATED),
            self._result(fetch_command.NO_KEY_TRANSLATED),
        ]
        self.command._UPDATED_BLOCKS = {"block1"}
        self.command._TOTAL_REQUESTS = 5

        with self.assertLogs(fetch_command.log, level="INFO") as logs:
            self.command._log_final_report({"block": {}})
        messages = [record.getMessage() for record in logs.records]

        self.assertIn("Translations updated: 2", messages)
        self.assertIn("Translations fetched without changes: 1", messages)
        self.assertIn("Translations fetched but not translated or reviewed yet: 2", messages)
        self.assertIn("Blocks updated: 1", messages)
        self.assertIn("Meta requests failed: 0 of 5.", messages)
        self.assertFalse(any(message.startswith("Request data dict") for message in messages))

    @patch.object(fetch_command.Command, "_check_and_update_translations")
    def test_invalid_response_is_counted_as_failed(self, mock_check):
        data_dict = {"source": {"target_block_versions": {"fr": "target"}}}
        responses = [
            None,
            {"response_source_block": "unknown", "mclanguage": "fr", "response_data": {}},
            {"response_source_block": "source", "mclanguage": "fr", "response_data": {}},
        ]

        with self.assertLogs(fetch_command.log, level="ERROR") as logs:
            self.command._update_response_translations_in_db(data_dict, responses)

        self.assertEqual(self.command._FAILED_REQUESTS, 2)
        mock_check.assert_called_once_with({}, "target", "fr")
        self.assertIn("response_source_block: unknown, target_language_code: fr", logs.records[0].getMessage())
