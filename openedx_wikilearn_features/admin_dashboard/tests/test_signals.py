"""
Tests for the report ready email sent from `admin_dashboard.signals`.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils.translation import override

from openedx_wikilearn_features.admin_dashboard.signals import send_report_ready_email

SIGNALS = "openedx_wikilearn_features.admin_dashboard.signals"


@override_settings(LANGUAGE_CODE="en")
@patch(f"{SIGNALS}.send_report_ready_email_task")
@patch(f"{SIGNALS}.UserPreference.get_value", return_value=None)
@patch(f"{SIGNALS}.CourseOverview.objects.filter")
class SendReportReadyEmailTest(TestCase):
    def setUp(self):
        self.instance = MagicMock(task_type="grade_course", course_id="course-v1:A+B+C")
        self.instance.requester.email = "requester@example.com"

    def _courses(self, *names):
        return [MagicMock(display_name=name) for name in names]

    def _sent(self, mock_task):
        mock_task.delay.assert_called_once()
        msg_class_key, data, subject, emails, language = mock_task.delay.call_args.args
        self.assertEqual(msg_class_key, "report_ready")
        self.assertEqual(emails, ["requester@example.com"])
        self.assertEqual(data["report_link"], "https://example.com/reports")
        return data["email_msg"], language

    def test_all_courses(self, mock_filter, mock_get_value, mock_task):
        mock_filter.return_value = []
        send_report_ready_email(self.instance, "https://example.com/reports")

        email_msg, language = self._sent(mock_task)
        self.assertEqual(email_msg, 'The "Grade Course" report you requested for all courses is ready.')
        self.assertEqual(language, "en")

    def test_one_course(self, mock_filter, mock_get_value, mock_task):
        mock_filter.return_value = self._courses("Intro")
        send_report_ready_email(self.instance, "https://example.com/reports")

        email_msg, _ = self._sent(mock_task)
        self.assertEqual(email_msg, 'The "Grade Course" report you requested for the course "Intro" is ready.')

    def test_many_courses(self, mock_filter, mock_get_value, mock_task):
        mock_filter.return_value = self._courses("Intro", "Advanced")
        send_report_ready_email(self.instance, "https://example.com/reports")

        email_msg, _ = self._sent(mock_task)
        self.assertEqual(
            email_msg, 'The "Grade Course" report you requested for the courses "Intro", "Advanced" is ready.'
        )

    def test_uses_requester_language(self, mock_filter, mock_get_value, mock_task):
        mock_filter.return_value = []
        mock_get_value.return_value = "es-419"

        with patch(f"{SIGNALS}.override", wraps=override) as mock_override:
            send_report_ready_email(self.instance, "https://example.com/reports")

        _, language = self._sent(mock_task)
        self.assertEqual(language, "es-419")
        mock_override.assert_called_once_with("es-419")
        self.assertEqual(mock_get_value.call_args.args[0], self.instance.requester)
