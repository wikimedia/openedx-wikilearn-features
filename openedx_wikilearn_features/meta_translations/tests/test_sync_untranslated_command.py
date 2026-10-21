"""
Tests for the `sync_untranslated_strings_to_meta_from_edx` command options.
"""
from unittest.mock import patch

from django.test import SimpleTestCase
from opaque_keys.edx.keys import CourseKey

from openedx_wikilearn_features.meta_translations.management.commands.sync_untranslated_strings_to_meta_from_edx import (
    Command,
)

COURSE_ID = "course-v1:A+B+C"


@patch.object(Command, "_get_request_data_list", return_value=[])
class BaseCourseKeyOptionTest(SimpleTestCase):
    def _run(self, *args):
        command = Command()
        options = vars(command.create_parser("manage.py", "sync_untranslated_strings_to_meta_from_edx").parse_args(args))
        command.handle(**options)

    def test_base_course_key_limits_the_courses(self, mock_get_request_data_list):
        self._run("--base-course-key", COURSE_ID)
        mock_get_request_data_list.assert_called_once_with([CourseKey.from_string(COURSE_ID)])

    def test_short_option(self, mock_get_request_data_list):
        self._run("-bck", COURSE_ID)
        mock_get_request_data_list.assert_called_once_with([CourseKey.from_string(COURSE_ID)])

    def test_without_base_course_key(self, mock_get_request_data_list):
        self._run()
        mock_get_request_data_list.assert_called_once_with([])
