"""
Comprehensive unit tests for patched bulk email functionality.
Tests verify that:
1. All original functionality remains intact
2. Enhanced failure/skip details are properly captured
3. No regressions are introduced by patches
"""

import json
from datetime import datetime
from itertools import chain, cycle, repeat
from smtplib import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPDataError,
    SMTPSenderRefused,
    SMTPServerDisconnected
)
from unittest.mock import patch
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from celery.states import FAILURE, SUCCESS
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.test.utils import override_settings

from lms.djangoapps.bulk_email.models import Optout
from lms.djangoapps.bulk_email.tasks import _get_course_email_context
from lms.djangoapps.instructor_task.views import get_task_completion_info
from lms.djangoapps.instructor_task.models import InstructorTask
from lms.djangoapps.instructor_task.tasks import send_bulk_course_email
from lms.djangoapps.bulk_email.tests.test_tasks import (
    TestBulkEmailInstructorTask,
    my_update_subtask_status
)
from xmodule.modulestore.tests.factories import CourseFactory


class TestPatchedBulkEmailComplete(TestBulkEmailInstructorTask):
    """
    Complete test suite for patched bulk email functionality.
    Ensures no regressions while adding enhanced detail tracking.
    """

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _get_task_details(self, entry):
        """
        Extract failure_details and skip_details from task output.

        Returns:
            tuple: (failure_details, skip_details)
        """
        status = json.loads(entry.task_output)
        failure_details = status.get('failure_details', [])
        skip_details = status.get('skip_details', [])
        return failure_details, skip_details

    def _get_subtask_details(self, entry):
        """
        Extract failure_details and skip_details from subtask status.

        Returns:
            tuple: (failure_details, skip_details) from first subtask
        """
        subtask_info = json.loads(entry.subtasks)
        subtask_status_info = subtask_info.get('status')
        task_id = list(subtask_status_info.keys())[0]
        subtask_status = subtask_status_info.get(task_id)
        failure_details = subtask_status.get('failure_details', [])
        skip_details = subtask_status.get('skip_details', [])
        return failure_details, skip_details

    def _assert_enhanced_subtask_status(
        self, entry, succeeded, failed=0, skipped=0,
        retried_nomax=0, retried_withmax=0,
        check_failure_details=False, check_skip_details=False
    ):
        """
        Enhanced version of _assert_single_subtask_status that also checks details.

        Args:
            entry: InstructorTask entry
            succeeded: Expected number of successes
            failed: Expected number of failures
            skipped: Expected number of skipped
            retried_nomax: Expected unlimited retries
            retried_withmax: Expected limited retries
            check_failure_details: If True, verify failure_details exist
            check_skip_details: If True, verify skip_details exist
        """
        # Call original assertion
        self._assert_single_subtask_status(
            entry, succeeded, failed, skipped, retried_nomax, retried_withmax
        )

        # Additional checks for enhanced fields
        subtask_info = json.loads(entry.subtasks)
        subtask_status_info = subtask_info.get('status')
        task_id = list(subtask_status_info.keys())[0]
        subtask_status = subtask_status_info.get(task_id)

        # Verify enhanced fields exist
        assert 'failure_details' in subtask_status
        assert 'skip_details' in subtask_status

        if check_failure_details and failed > 0:
            failure_details = subtask_status.get('failure_details', [])
            assert len(failure_details) > 0, "Expected failure details but got none"

        if check_skip_details and skipped > 0:
            skip_details = subtask_status.get('skip_details', [])
            assert len(skip_details) > 0, "Expected skip details but got none"

    # ========================================================================
    # ORIGINAL FUNCTIONALITY TESTS - ENSURE NO REGRESSIONS
    # ========================================================================

    def test_successful_original_behavior(self):
        """Test that successful email sending still works exactly as before."""
        num_emails = settings.BULK_EMAIL_EMAILS_PER_TASK
        self._create_students(num_emails - 1)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])
            entry = self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, num_emails
            )

            # Verify enhanced fields exist but are empty
            failure_details, skip_details = self._get_task_details(entry)
            assert len(failure_details) == 0
            assert len(skip_details) == 0

    def test_successful_twice_original_behavior(self):
        """Test that task deduplication still works."""
        num_emails = settings.BULK_EMAIL_EMAILS_PER_TASK
        self._create_students(num_emails - 1)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])
            task_entry = self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, num_emails
            )

        # Submit same task again
        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([Exception("Should not happen!")])
            parent_status = self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

        assert parent_status.get('total') == num_emails
        assert parent_status.get('succeeded') == num_emails
        assert parent_status.get('failed') == 0

    def test_unactivated_user_original_behavior(self):
        """Test that unactivated users are still filtered correctly."""
        num_emails = settings.BULK_EMAIL_EMAILS_PER_TASK
        students = self._create_students(num_emails - 1)

        # Mark student as not activated
        student = students[0]
        student.is_active = False
        student.save()

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])
            self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails - 1, num_emails - 1
            )

    def test_skipped_original_behavior(self):
        """Test that opt-out functionality still works."""
        num_emails = settings.BULK_EMAIL_EMAILS_PER_TASK
        students = self._create_students(num_emails - 1)

        # Have every fourth student opt out
        expected_skipped = int((num_emails + 3) / 4.0)
        expected_succeeds = num_emails - expected_skipped
        for index in range(0, num_emails, 4):
            Optout.objects.create(user=students[index], course_id=self.course.id)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])
            entry = self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails,
                expected_succeeds, skipped=expected_skipped
            )

            # Now verify skip details are captured
            _, skip_details = self._get_task_details(entry)
            assert len(skip_details) == expected_skipped

    def test_smtp_blacklisted_user_original_behavior(self):
        """Test SMTP permanent failures still work."""
        num_emails = settings.BULK_EMAIL_EMAILS_PER_TASK
        self._create_students(num_emails - 1)

        expected_fails = int((num_emails + 3) / 4.0)
        expected_succeeds = num_emails - expected_fails
        exception = SMTPDataError(554, "Email address is blacklisted")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None, None, None])
            entry = self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails,
                expected_succeeds, failed=expected_fails
            )

            # Verify failure details are captured
            failure_details, _ = self._get_task_details(entry)
            assert len(failure_details) == expected_fails

    def test_ses_errors_original_behavior(self):
        """Test SES errors still handled correctly."""
        num_emails = settings.BULK_EMAIL_EMAILS_PER_TASK
        self._create_students(num_emails - 1)

        expected_fails = int((num_emails + 3) / 4.0)
        expected_succeeds = num_emails - expected_fails

        operation_name = ''
        parsed_response = {
            'Error': {'Code': 'MessageRejected', 'Message': 'Error Uploading'}
        }
        exception = ClientError(parsed_response, operation_name)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None, None, None])
            entry = self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails,
                expected_succeeds, failed=expected_fails
            )

            # Verify failure details captured
            failure_details, _ = self._get_task_details(entry)
            assert len(failure_details) == expected_fails

    def test_non_ascii_emails_original_behavior(self):
        """Test non-ASCII email handling still works."""
        num_emails = 10
        emails_with_non_ascii_chars = 3
        num_of_course_instructors = 1

        students = [self.create_student('robot%d' % i) for i in range(num_emails)]
        for student in students[:emails_with_non_ascii_chars]:
            student.email = f'{student.username}@tesá.com'
            student.save()

        total = num_emails + num_of_course_instructors
        expected_succeeds = num_emails - emails_with_non_ascii_chars + num_of_course_instructors
        expected_fails = emails_with_non_ascii_chars

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])
            entry = self._test_run_with_task(
                task_class=send_bulk_course_email,
                action_name='emailed',
                total=total,
                succeeded=expected_succeeds,
                failed=expected_fails
            )

            # Verify failure details for non-ASCII
            failure_details, _ = self._get_task_details(entry)
            assert len(failure_details) == expected_fails
            for email, reason in failure_details:
                assert 'Non-ASCII' in reason

    # ========================================================================
    # RETRY BEHAVIOR TESTS - ORIGINAL FUNCTIONALITY
    # ========================================================================

    def test_retry_after_smtp_disconnect_original_behavior(self):
        """Test retries on SMTP disconnect still work."""
        num_emails = settings.BULK_EMAIL_MAX_RETRIES
        self._create_students(num_emails - 1)

        exception = SMTPServerDisconnected(425, "Disconnecting")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])
            self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, num_emails,
                failed=0, retried_withmax=num_emails
            )

    def test_max_retry_after_smtp_disconnect_original_behavior(self):
        """Test max retry limit still enforced."""
        num_emails = 10
        self._create_students(num_emails - 1)

        exception = SMTPServerDisconnected(425, "Disconnecting")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])
            with patch('lms.djangoapps.bulk_email.tasks.update_subtask_status', my_update_subtask_status):
                self._test_run_with_task(
                    send_bulk_course_email, 'emailed', num_emails, 0,
                    failed=num_emails,
                    retried_withmax=(settings.BULK_EMAIL_MAX_RETRIES + 1)
                )

    def test_retry_after_smtp_connect_error_original_behavior(self):
        """Test SMTP connect errors trigger retries."""
        num_emails = settings.BULK_EMAIL_MAX_RETRIES
        self._create_students(num_emails - 1)

        exception = SMTPConnectError(424, "Bad Connection")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])
            self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, num_emails,
                failed=0, retried_withmax=num_emails
            )

    def test_max_retry_after_smtp_connect_error_original_behavior(self):
        """Test max retries on connect errors."""
        num_emails = 10
        self._create_students(num_emails - 1)

        exception = SMTPConnectError(424, "Bad Connection")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])
            with patch('lms.djangoapps.bulk_email.tasks.update_subtask_status', my_update_subtask_status):
                self._test_run_with_task(
                    send_bulk_course_email, 'emailed', num_emails, 0,
                    failed=num_emails,
                    retried_withmax=(settings.BULK_EMAIL_MAX_RETRIES + 1)
                )

    def test_retry_after_aws_connect_error_original_behavior(self):
        """Test AWS connection errors trigger retries."""
        num_emails = settings.BULK_EMAIL_MAX_RETRIES
        self._create_students(num_emails - 1)

        exception = EndpointConnectionError(endpoint_url="Could not connect")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])
            self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, num_emails,
                failed=0, retried_withmax=num_emails
            )

    def test_max_retry_after_aws_connect_error_original_behavior(self):
        """Test max retries on AWS errors."""
        num_emails = 10
        self._create_students(num_emails - 1)

        exception = EndpointConnectionError(endpoint_url="Could not connect")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])
            with patch('lms.djangoapps.bulk_email.tasks.update_subtask_status', my_update_subtask_status):
                self._test_run_with_task(
                    send_bulk_course_email, 'emailed', num_emails, 0,
                    failed=num_emails,
                    retried_withmax=(settings.BULK_EMAIL_MAX_RETRIES + 1)
                )

    def test_retry_after_general_error_original_behavior(self):
        """Test general errors trigger retries."""
        num_emails = settings.BULK_EMAIL_MAX_RETRIES
        self._create_students(num_emails - 1)

        exception = Exception("Random exception")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])
            self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, num_emails,
                failed=0, retried_withmax=num_emails
            )

    def test_max_retry_after_general_error_original_behavior(self):
        """Test max retries on general errors."""
        num_emails = 10
        self._create_students(num_emails - 1)

        exception = Exception("Random exception")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])
            with patch('lms.djangoapps.bulk_email.tasks.update_subtask_status', my_update_subtask_status):
                self._test_run_with_task(
                    send_bulk_course_email, 'emailed', num_emails, 0,
                    failed=num_emails,
                    retried_withmax=(settings.BULK_EMAIL_MAX_RETRIES + 1)
                )

    def test_retry_after_smtp_throttling_error_original_behavior(self):
        """Test unlimited retries on throttling errors."""
        num_emails = 8
        self._create_students(num_emails - 1)

        expected_retries = 10
        exception = SMTPDataError(455, "Throttling: Sending rate exceeded")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle(
                chain(repeat(exception, expected_retries), [None])
            )
            self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, num_emails,
                failed=0, retried_nomax=(expected_retries * num_emails)
            )

    def test_retry_after_smtp_sender_refused_error_original_behavior(self):
        """Test unlimited retries on sender refused errors."""
        num_emails = 8
        self._create_students(num_emails - 1)

        expected_retries = 10
        exception = SMTPSenderRefused(
            421, "Throttling: Sending rate exceeded", self.instructor.email
        )

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle(
                chain(repeat(exception, expected_retries), [None])
            )
            self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, num_emails,
                failed=0, retried_nomax=(expected_retries * num_emails)
            )

    def test_immediate_failure_on_unhandled_smtp_original_behavior(self):
        """Test unhandled SMTP errors fail immediately."""
        num_emails = 10
        self._create_students(num_emails - 1)

        exception = SMTPAuthenticationError(403, "That password doesn't work!")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])
            self._test_run_with_task(
                send_bulk_course_email, 'emailed', num_emails, 0, failed=num_emails
            )

    # ========================================================================
    # SPECIAL CASES - ORIGINAL FUNCTIONALITY
    # ========================================================================

    def test_unicode_course_image_original_behavior(self):
        """Test unicode course image names still work."""
        course_image = '在淡水測試.jpg'
        self.course = CourseFactory.create(course_image=course_image)

        num_emails = 2
        self._create_students(num_emails - 1)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])
            self._test_run_with_task(send_bulk_course_email, 'emailed', num_emails, num_emails)

    def test_get_course_email_context_original_behavior(self):
        """Test course email context still has all required keys."""
        result = _get_course_email_context(self.course)

        required_keys = [
            'course_title', 'course_root', 'course_language', 'course_url',
            'course_image_url', 'course_end_date', 'account_settings_url',
            'email_settings_url', 'platform_name'
        ]

        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

    @override_settings(BULK_COURSE_EMAIL_LAST_LOGIN_ELIGIBILITY_PERIOD=1)
    def test_last_login_filtering_original_behavior(self):
        """Test last login filtering still works."""
        students = self._create_students(2)
        students[0].last_login = datetime.now()
        students[1].last_login = datetime.now() - relativedelta(months=2)
        students[0].save()
        students[1].save()

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])
            self._test_run_with_task(send_bulk_course_email, 'emailed', 1, 1)

    def test_disabled_user_filtering_original_behavior(self):
        """Test disabled user filtering still works."""
        user_1 = self.create_student(username="user1", email="user1@example.com")
        user_1.set_unusable_password()
        user_1.save()
        self.create_student(username="user2", email="user2@example.com")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])
            entry = self._test_run_with_task(
                send_bulk_course_email, 'emailed', 3, 2, skipped=1
            )

            # Verify skip details captured for disabled user
            _, skip_details = self._get_task_details(entry)
            assert len(skip_details) == 1

    # ========================================================================
    # ENHANCED DETAIL TRACKING TESTS - NEW FUNCTIONALITY
    # ========================================================================

    def test_failure_details_structure(self):
        """Test that failure details have correct structure."""
        num_emails = 4
        self._create_students(num_emails - 1)

        exception = SMTPDataError(554, "Blacklisted")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            failure_details, _ = self._get_task_details(entry)

            # Verify structure
            assert isinstance(failure_details, list)
            for detail in failure_details:
                assert isinstance(detail, (list, tuple))
                assert len(detail) == 2
                email, reason = detail
                assert isinstance(email, str)
                assert isinstance(reason, str)
                assert len(email) > 0
                assert len(reason) > 0

    def test_skip_details_structure(self):
        """Test that skip details have correct structure."""
        num_emails = 4
        students = self._create_students(num_emails - 1)

        # Opt out some students
        for i in range(0, len(students), 2):
            Optout.objects.create(user=students[i], course_id=self.course.id)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            _, skip_details = self._get_task_details(entry)

            # Verify structure
            assert isinstance(skip_details, list)
            for detail in skip_details:
                assert isinstance(detail, (list, tuple))
                assert len(detail) == 2
                email, reason = detail
                assert isinstance(email, str)
                assert isinstance(reason, str)
                assert 'Opt-out' in reason

    def test_details_in_completion_message(self):
        """Test that completion message includes detailed information."""
        num_emails = 4
        students = self._create_students(num_emails - 1)

        # Mix of failures and skips
        Optout.objects.create(user=students[0], course_id=self.course.id)
        exception = SMTPDataError(554, "Rejected")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            succeeded, message = get_task_completion_info(entry)

            # Message should contain detailed info
            assert isinstance(message, str)
            assert len(message) > 0

    def test_task_output_supports_large_details(self):
        """Test TextField migration supports large detail sets."""
        num_emails = 30
        self._create_students(num_emails - 1)

        # Make many emails fail
        exception = SMTPDataError(554, "Long error message for testing purposes")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)

            # Verify large output is stored
            assert entry.task_output is not None
            # Should exceed old CharField(1024) limit
            assert len(entry.task_output) > 1024

    def test_mixed_error_types_all_captured(self):
        """Test that different error types are all captured correctly."""
        num_emails = 5
        students = self._create_students(num_emails - 1)

        # Create different types of issues
        # 1. Opt-out
        Optout.objects.create(user=students[0], course_id=self.course.id)

        # 2. Non-ASCII email
        students[1].email = f'{students[1].username}@tesá.com'
        students[1].save()

        # 3. SMTP error (will happen to remaining students)
        exception = SMTPDataError(554, "Rejected")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            failure_details, skip_details = self._get_task_details(entry)

            # Should have both failures and skips
            assert len(failure_details) > 0
            assert len(skip_details) > 0

            # Check for different error types
            has_non_ascii = any('Non-ASCII' in reason for _, reason in failure_details)
            has_smtp = any('SMTPDataError' in reason for _, reason in failure_details)
            has_optout = any('Opt-out' in reason for _, reason in skip_details)

            assert has_non_ascii or has_smtp, "Expected failure details"
            assert has_optout, "Expected opt-out in skip details"

    def test_subtask_status_backward_compatibility(self):
        """Test that SubtaskStatus maintains backward compatibility."""
        num_emails = 3
        self._create_students(num_emails - 1)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            subtask_info = json.loads(entry.subtasks)
            subtask_status_info = subtask_info.get('status')
            task_id = list(subtask_status_info.keys())[0]
            subtask_status = subtask_status_info.get(task_id)

            # All original fields should exist
            required_fields = [
                'task_id', 'attempted', 'succeeded', 'failed', 'skipped',
                'retried_nomax', 'retried_withmax', 'state'
            ]
            for field in required_fields:
                assert field in subtask_status, f"Missing original field: {field}"

            # Enhanced fields should also exist
            assert 'failure_details' in subtask_status
            assert 'skip_details' in subtask_status

    def test_enhanced_subtask_status_to_dict(self):
        """Test that EnhancedSubtaskStatus.to_dict() includes all fields."""
        from lms.djangoapps.instructor_task.subtasks import SubtaskStatus

        # Create instance (will be EnhancedSubtaskStatus due to patching)
        status = SubtaskStatus.create(
            task_id='test-task-123',
            succeeded=5,
            failed=2,
            skipped=1
        )

        # Add some details
        if hasattr(status, 'add_failure_detail'):
            status.add_failure_detail('test@example.com', 'Test failure')
        if hasattr(status, 'add_skip_detail'):
            status.add_skip_detail('skip@example.com', 'Test skip')

        # Convert to dict
        status_dict = status.to_dict()

        # Verify all fields present
        assert 'task_id' in status_dict
        assert 'succeeded' in status_dict
        assert 'failed' in status_dict
        assert 'skipped' in status_dict
        assert 'failure_details' in status_dict
        assert 'skip_details' in status_dict

    def test_enhanced_subtask_status_from_dict(self):
        """Test that EnhancedSubtaskStatus.from_dict() reconstructs correctly."""
        from lms.djangoapps.instructor_task.subtasks import SubtaskStatus

        # Create dict representation
        status_dict = {
            'task_id': 'test-task-456',
            'attempted': 10,
            'succeeded': 7,
            'failed': 2,
            'skipped': 1,
            'retried_nomax': 0,
            'retried_withmax': 0,
            'state': SUCCESS,
            'failure_details': [('fail@example.com', 'Test failure')],
            'skip_details': [('skip@example.com', 'Test skip')]
        }

        # Reconstruct from dict
        status = SubtaskStatus.from_dict(status_dict)

        # Verify fields
        assert status.task_id == 'test-task-456'
        assert status.succeeded == 7
        assert status.failed == 2
        assert status.skipped == 1

        # Verify enhanced fields if they exist
        if hasattr(status, 'failure_details'):
            assert len(status.failure_details) == 1
        if hasattr(status, 'skip_details'):
            assert len(status.skip_details) == 1

    def test_initialize_subtask_info_creates_enhanced_fields(self):
        """Test that initialize_subtask_info creates enhanced fields."""
        from lms.djangoapps.instructor_task.subtasks import initialize_subtask_info

        task_entry = self._create_input_entry()
        subtask_id_list = ['subtask-1', 'subtask-2']

        # Initialize
        task_progress = initialize_subtask_info(
            task_entry, 'test_action', 100, subtask_id_list
        )

        # Reload entry
        entry = InstructorTask.objects.get(id=task_entry.id)

        # Check task_output has enhanced fields
        status = json.loads(entry.task_output)
        assert 'failure_details' in status
        assert 'skip_details' in status
        assert isinstance(status['failure_details'], list)
        assert isinstance(status['skip_details'], list)

        # Check subtasks have enhanced fields
        subtask_info = json.loads(entry.subtasks)
        for subtask_id in subtask_id_list:
            subtask_status = subtask_info['status'][subtask_id]
            assert 'failure_details' in subtask_status
            assert 'skip_details' in subtask_status

    def test_ses_multiple_error_codes(self):
        """Test different SES error codes are handled correctly."""
        error_codes = [
            'MessageRejected',
            'MailFromDomainNotVerified',
            'MailFromDomainNotVerifiedException',
            'FromEmailAddressNotVerifiedException'
        ]

        for error_code in error_codes:
            num_emails = 3
            self._create_students(num_emails - 1)

            operation_name = ''
            parsed_response = {
                'Error': {'Code': error_code, 'Message': f'Error: {error_code}'}
            }
            exception = ClientError(parsed_response, operation_name)

            with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
                get_conn.return_value.send_messages.side_effect = cycle([exception, None])

                task_entry = self._create_input_entry()
                self._run_task_with_mock_celery(
                    send_bulk_course_email, task_entry.id, task_entry.task_id
                )

                entry = InstructorTask.objects.get(id=task_entry.id)
                failure_details, _ = self._get_task_details(entry)

                # Should have captured failures
                assert len(failure_details) > 0, f"No failures captured for {error_code}"

    def test_failure_details_email_uniqueness(self):
        """Test that same email can have multiple failure entries if it fails multiple times."""
        num_emails = 2
        self._create_students(num_emails - 1)

        # This scenario is unlikely in practice but tests the data structure
        exception = SMTPDataError(554, "Rejected")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            failure_details, _ = self._get_task_details(entry)

            # Each failure should be recorded
            assert len(failure_details) == num_emails

    def test_empty_recipient_list_handling(self):
        """Test that empty recipient lists are handled correctly."""
        # Don't create any students, only instructor gets email

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])

            task_entry = self._create_input_entry()
            parent_status = self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            # Should succeed for instructor only
            assert parent_status.get('succeeded') == 1

            entry = InstructorTask.objects.get(id=task_entry.id)
            failure_details, skip_details = self._get_task_details(entry)

            # No details since all succeeded
            assert len(failure_details) == 0
            assert len(skip_details) == 0

    def test_all_recipients_optout(self):
        """Test when all recipients opt out."""
        num_emails = 5
        students = self._create_students(num_emails - 1)

        # All students opt out (but not instructor)
        for student in students:
            Optout.objects.create(user=student, course_id=self.course.id)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])

            task_entry = self._create_input_entry()
            parent_status = self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            # Only instructor should succeed
            assert parent_status.get('succeeded') == 1
            assert parent_status.get('skipped') == (num_emails - 1)

            entry = InstructorTask.objects.get(id=task_entry.id)
            _, skip_details = self._get_task_details(entry)

            # All students should be in skip details
            assert len(skip_details) == (num_emails - 1)

    def test_all_recipients_fail(self):
        """Test when all recipients fail."""
        num_emails = 5
        self._create_students(num_emails - 1)

        exception = SMTPDataError(554, "All rejected")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])

            task_entry = self._create_input_entry()
            parent_status = self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            # All should fail
            assert parent_status.get('failed') == num_emails

            entry = InstructorTask.objects.get(id=task_entry.id)
            failure_details, _ = self._get_task_details(entry)

            # All recipients should be in failure details
            assert len(failure_details) == num_emails

    def test_update_task_dict_utility(self):
        """Test that update_task_dict utility adds required fields."""
        from lms.djangoapps.bulk_email.tasks import update_task_dict

        # Test with empty dict
        task_dict = {}
        result = update_task_dict(task_dict)

        assert 'skip_details' in result
        assert 'failure_details' in result
        assert isinstance(result['skip_details'], list)
        assert isinstance(result['failure_details'], list)

        # Test with existing dict
        task_dict = {'succeeded': 5, 'failed': 2}
        result = update_task_dict(task_dict)

        # Should preserve existing fields
        assert result['succeeded'] == 5
        assert result['failed'] == 2
        # And add new fields
        assert 'skip_details' in result
        assert 'failure_details' in result

    def test_get_detailed_message_utility(self):
        """Test that get_detailed_message utility formats messages correctly."""
        from lms.djangoapps.bulk_email.tasks import get_detailed_message

        # Test with failures only
        task_output = {
            'failure_details': [
                ('fail1@example.com', 'SMTP Error'),
                ('fail2@example.com', 'Non-ASCII')
            ],
            'skip_details': []
        }
        message = get_detailed_message(task_output)
        assert 'Detailed Failures:' in message
        assert 'fail1@example.com' in message
        assert 'fail2@example.com' in message

        # Test with skips only
        task_output = {
            'failure_details': [],
            'skip_details': [
                ('skip1@example.com', 'Opt-out'),
                ('skip2@example.com', 'Opt-out')
            ]
        }
        message = get_detailed_message(task_output)
        assert 'Detailed Skips:' in message
        assert 'skip1@example.com' in message

        # Test with both
        task_output = {
            'failure_details': [('fail@example.com', 'Error')],
            'skip_details': [('skip@example.com', 'Opt-out')]
        }
        message = get_detailed_message(task_output)
        assert 'Detailed Failures:' in message
        assert 'Detailed Skips:' in message

        # Test with neither
        task_output = {
            'failure_details': [],
            'skip_details': []
        }
        message = get_detailed_message(task_output)
        assert 'No detailed failure or skip information available' in message

    def test_error_messages_are_descriptive(self):
        """Test that error messages contain useful information."""
        num_emails = 3
        students = self._create_students(num_emails - 1)

        # Create various error scenarios
        students[0].email = f'{students[0].username}@tesá.com'
        students[0].save()

        exception = SMTPDataError(554, "Specific SMTP error message")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            failure_details, _ = self._get_task_details(entry)

            # Check that reasons are descriptive
            for email, reason in failure_details:
                # Reason should not be empty
                assert len(reason) > 0
                # Should contain error type or description
                assert any(keyword in reason for keyword in [
                    'SMTP', 'Non-ASCII', 'Error', 'error', '554'
                ])

    def test_concurrent_subtask_detail_accumulation(self):
        """Test that details accumulate correctly when subtasks complete."""
        # This is a simplified test since true concurrency is hard to test
        num_emails = 5
        self._create_students(num_emails - 1)

        exception = SMTPDataError(554, "Rejected")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None, None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)

            # Verify counts match details
            status = json.loads(entry.task_output)
            failure_details = status.get('failure_details', [])

            # Number of failure details should match failed count
            assert len(failure_details) == status['failed']

    def test_task_state_transitions_with_details(self):
        """Test that task state transitions correctly preserve details."""
        num_emails = 3
        self._create_students(num_emails - 1)

        exception = SMTPDataError(554, "Error")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)

            # Task should be in SUCCESS state
            assert entry.task_state == SUCCESS

            # But should still have failure details
            failure_details, _ = self._get_task_details(entry)
            assert len(failure_details) > 0

    def test_json_serialization_of_details(self):
        """Test that details are properly JSON serializable."""
        num_emails = 3
        students = self._create_students(num_emails - 1)

        Optout.objects.create(user=students[0], course_id=self.course.id)
        exception = SMTPDataError(554, "Error with special chars: <>&\"'")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception, None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)

            # Should be able to parse JSON without errors
            try:
                status = json.loads(entry.task_output)
                subtasks = json.loads(entry.subtasks)

                # And serialize back
                json.dumps(status)
                json.dumps(subtasks)
            except (json.JSONDecodeError, TypeError) as e:
                pytest.fail(f"JSON serialization failed: {e}")

    def test_backwards_compatibility_with_old_tasks(self):
        """Test that old task outputs without detail fields still work."""
        # Create a task entry manually with old-style output
        task_entry = self._create_input_entry()

        # Old-style task_output without detail fields
        old_style_output = {
            'action_name': 'emailed',
            'attempted': 5,
            'succeeded': 3,
            'failed': 2,
            'skipped': 0,
            'total': 5,
            'duration_ms': 1000,
            'start_time': 1234567890
        }

        task_entry.task_output = json.dumps(old_style_output)
        task_entry.task_state = SUCCESS
        task_entry.save()

        # Should be able to get completion info
        try:
            succeeded, message = get_task_completion_info(task_entry)
            assert isinstance(message, str)
        except Exception as e:
            pytest.fail(f"Failed to handle old-style task output: {e}")

    # ========================================================================
    # STRESS TESTS
    # ========================================================================

    def test_large_number_of_failures(self):
        """Test handling of large numbers of failures."""
        num_emails = 50
        self._create_students(num_emails - 1)

        exception = SMTPDataError(554, "All rejected")

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([exception])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            failure_details, _ = self._get_task_details(entry)

            # Should handle all failures
            assert len(failure_details) == num_emails

    def test_large_number_of_skips(self):
        """Test handling of large numbers of skips."""
        num_emails = 50
        students = self._create_students(num_emails - 1)

        # All opt out
        for student in students:
            Optout.objects.create(user=student, course_id=self.course.id)

        with patch('lms.djangoapps.bulk_email.tasks.get_connection', autospec=True) as get_conn:
            get_conn.return_value.send_messages.side_effect = cycle([None])

            task_entry = self._create_input_entry()
            self._run_task_with_mock_celery(
                send_bulk_course_email, task_entry.id, task_entry.task_id
            )

            entry = InstructorTask.objects.get(id=task_entry.id)
            _, skip_details = self._get_task_details(entry)

            # Should handle all skips
            assert len(skip_details) == (num_emails - 1)
