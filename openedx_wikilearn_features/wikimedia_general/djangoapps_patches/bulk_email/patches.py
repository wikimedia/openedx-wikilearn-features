
import logging
import time
from collections import Counter

from smtplib import SMTPConnectError, SMTPDataError, SMTPException, SMTPSenderRefused, SMTPServerDisconnected
from time import sleep

from botocore.exceptions import ClientError, EndpointConnectionError
from celery.states import FAILURE, RETRY, SUCCESS
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import get_connection
from eventtracking import tracker

from common.djangoapps.util.string_utils import _has_non_ascii_characters
from lms.djangoapps.bulk_email.api import get_unsubscribed_link
from lms.djangoapps.bulk_email.messages import ACEEmail, DjangoEmail
from lms.djangoapps.bulk_email.models import CourseEmail, Optout
from lms.djangoapps.bulk_email.toggles import (
    is_bulk_email_edx_ace_enabled,
    is_email_use_course_id_from_for_bulk_enabled
)
from lms.djangoapps.instructor_task.models import InstructorTask
from lms.djangoapps.bulk_email.tasks import (
    _submit_for_retry,
    _filter_disabled_users_from_recipients,
    _filter_optouts_from_recipients,
    _get_source_address
)
from openedx.core.djangoapps.ace_common.template_context import get_base_template_context


log = logging.getLogger('edx.celery.task')


# Errors that an individual email is failing to be sent, and should just
# be treated as a fail.
SINGLE_EMAIL_FAILURE_ERRORS = (
    ClientError
)

# Exceptions that, if caught, should cause the task to be re-tried.
# These errors will be caught a limited number of times before the task fails.
LIMITED_RETRY_ERRORS = (
    SMTPConnectError,
    SMTPServerDisconnected,
    EndpointConnectionError,
)

# Errors that indicate that a mailing task should be retried without limit.
# An example is if email is being sent too quickly, but may succeed if sent
# more slowly.  When caught by a task, it triggers an exponential backoff and retry.
# Retries happen continuously until the email is sent.
# Note that the (SMTPDataErrors and SMTPSenderRefused)  here are only those within the 4xx range.
# Those not in this range (i.e. in the 5xx range) are treated as hard failures
# and thus like SINGLE_EMAIL_FAILURE_ERRORS.
INFINITE_RETRY_ERRORS = (
    SMTPDataError,
    SMTPSenderRefused,
    ClientError
)

# Errors that are known to indicate an inability to send any more emails,
# and should therefore not be retried.  For example, exceeding a quota for emails.
# Also, any SMTP errors that are not explicitly enumerated above.
BULK_EMAIL_FAILURE_ERRORS = (
    ClientError,
    SMTPException
)


def _send_course_email(entry_id, email_id, to_list, global_email_context, subtask_status):  # lint-amnesty, pylint: disable=too-many-statements
    """
    Performs the email sending task.

    Sends an email to a list of recipients.

    Inputs are:
      * `entry_id`: id of the InstructorTask object to which progress should be recorded.
      * `email_id`: id of the CourseEmail model that is to be emailed.
      * `to_list`: list of recipients.  Each is represented as a dict with the following keys:
        - 'profile__name': full name of User.
        - 'email': email address of User.
        - 'pk': primary key of User model.
      * `global_email_context`: dict containing values that are unique for this email but the same
        for all recipients of this email.  This dict is to be used to fill in slots in email
        template.  It does not include 'name' and 'email', which will be provided by the to_list.
      * `subtask_status` : object of class SubtaskStatus representing current status.

    Sends to all addresses contained in to_list that are not also in the Optout table.
    Emails are sent multi-part, in both plain text and html.

    Returns a tuple of two values:
      * First value is a SubtaskStatus object which represents current progress at the end of this call.

      * Second value is an exception returned by the innards of the method, indicating a fatal error.
        In this case, the number of recipients that were not sent have already been added to the
        'failed' count above.
    """

    print("\n\n\n\n\n\nUSING PATCHED FUNCTION\n\n\n\n\n")
    # Get information from current task's request:
    parent_task_id = InstructorTask.objects.get(pk=entry_id).task_id
    task_id = subtask_status.task_id
    total_recipients = len(to_list)
    recipient_num = 0
    total_recipients_successful = 0
    total_recipients_failed = 0
    recipients_info = Counter()

    log.info(
        f"BulkEmail ==> Task: {parent_task_id}, SubTask: {task_id}, EmailId: {email_id}, "
        f"TotalRecipients: {total_recipients}, ace_enabled: {is_bulk_email_edx_ace_enabled()}"
    )

    try:
        course_email = CourseEmail.objects.get(id=email_id)
    except CourseEmail.DoesNotExist as exc:
        log.exception(
            f"BulkEmail ==> Task: {parent_task_id}, SubTask: {task_id}, EmailId: {email_id}, Could not find email to "
            "send."
        )
        raise exc
    tracker.emit(
        'edx.bulk_email.created',
        {
            'course_id': str(course_email.course_id),
            'to_list': [user_obj.get('email', '') for user_obj in to_list],
            'total_recipients': total_recipients,
            'ace_enabled_for_bulk_email': is_bulk_email_edx_ace_enabled(),
        }
    )
    # Exclude optouts (if not a retry):
    # Note that we don't have to do the optout logic at all if this is a retry,
    # because we have presumably already performed the optout logic on the first
    # attempt.  Anyone on the to_list on a retry has already passed the filter
    # that existed at that time, and we don't need to keep checking for changes
    # in the Optout list.
    if subtask_status.get_retry_count() == 0:
        to_list, num_optout = _filter_optouts_from_recipients(to_list, course_email.course_id)
        filtered_to_list, num_disabled = _filter_disabled_users_from_recipients(to_list, str(course_email.course_id))
        subtask_status.increment(skipped=num_optout + num_disabled)

        # Retrieve the list of opt-outs by comparing the original to_list and the filtered_to_list
        optout_list = [recipient for recipient in to_list if recipient not in filtered_to_list]

        for recipient in optout_list:
            skip_reason = "Opt-out by"
            subtask_status.add_skip_detail(recipient['email'], skip_reason)

        # Now, filtered_to_list contains recipients who didn't opt out
        to_list = filtered_to_list

    course_title = global_email_context['course_title']
    course_language = global_email_context['course_language']

    # If EMAIL_USE_COURSE_ID_FROM_FOR_BULK is False, use the default email from address.
    # Otherwise compute a custom from address
    if not is_email_use_course_id_from_for_bulk_enabled():
        from_addr = settings.BULK_EMAIL_DEFAULT_FROM_EMAIL or settings.DEFAULT_FROM_EMAIL
    else:
        # use the email from address in the CourseEmail, if it is present, otherwise compute it.
        from_addr = course_email.from_addr or _get_source_address(course_email.course_id, course_title, course_language)

    site = Site.objects.get_current()
    try:
        connection = get_connection()
        connection.open()

        # Define context values to use in all course emails:
        email_context = {'name': '', 'email': '', 'course_email': course_email, 'from_address': from_addr}
        template_context = get_base_template_context(site)
        email_context.update(global_email_context)
        email_context.update(template_context)

        start_time = time.time()
        while to_list:
            # Update context with user-specific values from the user at the end of the list.
            # At the end of processing this user, they will be popped off of the to_list.
            # That way, the to_list will always contain the recipients remaining to be emailed.
            # This is convenient for retries, which will need to send to those who haven't
            # yet been emailed, but not send to those who have already been sent to.
            recipient_num += 1
            current_recipient = to_list[-1]
            email = current_recipient['email']
            user_id = current_recipient['pk']
            profile_name = current_recipient['profile__name']
            if _has_non_ascii_characters(email):
                to_list.pop()
                total_recipients_failed += 1
                log.warning(
                    f"BulkEmail ==> Skipping course email to user {current_recipient['pk']} with email_id {email_id}. "
                    "The email address contains non-ASCII characters."
                )
                subtask_status.increment(failed=1)
                failure_reason = "Non-ASCII characters in email address"
                subtask_status.add_failure_detail(email, failure_reason)
                continue

            email_context['email'] = email
            email_context['name'] = profile_name
            email_context['user_id'] = user_id
            email_context['course_id'] = str(course_email.course_id)
            email_context['unsubscribe_link'] = get_unsubscribed_link(current_recipient['username'],
                                                                      str(course_email.course_id))
            email_context['unsubscribe_text'] = 'Unsubscribe from course updates for this course'
            email_context['disclaimer'] = (
                "You are receiving this email because you are enrolled in the "
                f"{email_context['platform_name']} course {email_context['course_title']}"
            )

            if is_bulk_email_edx_ace_enabled():
                message = ACEEmail(site, email_context)
            else:
                message = DjangoEmail(connection, course_email, email_context)
            # Throttle if we have gotten the rate limiter.  This is not very high-tech,
            # but if a task has been retried for rate-limiting reasons, then we sleep
            # for a period of time between all emails within this task.  Choice of
            # the value depends on the number of workers that might be sending email in
            # parallel, and what the SES throttle rate is.
            if subtask_status.retried_nomax > 0:
                sleep(settings.BULK_EMAIL_RETRY_DELAY_BETWEEN_SENDS)

            try:
                log.info(
                    f"BulkEmail ==> Task: {parent_task_id}, SubTask: {task_id}, EmailId: {email_id}, Recipient num: "
                    f"{recipient_num}/{total_recipients}, Recipient UserId: {current_recipient['pk']}"
                )
                message.send()
            except (SMTPDataError, SMTPSenderRefused) as exc:
                # According to SMTP spec, we'll retry error codes in the 4xx range.  5xx range indicates hard failure.
                total_recipients_failed += 1
                log.exception(
                    f"BulkEmail ==> Status: Failed({exc.smtp_error}), Task: {parent_task_id}, SubTask: {task_id}, "
                    f"EmailId: {email_id}, Recipient num: {recipient_num}/{total_recipients}, Recipient UserId: "
                    f"{current_recipient['pk']}"
                )
                if exc.smtp_code >= 400 and exc.smtp_code < 500:  # lint-amnesty, pylint: disable=no-else-raise
                    # This will cause the outer handler to catch the exception and retry the entire task.
                    raise exc
                else:
                    # This will fall through and not retry the message.
                    log.warning(
                        f"BulkEmail ==> Task: {parent_task_id}, SubTask: {task_id}, EmailId: {email_id}, Recipient "
                        f"num: {recipient_num}/{total_recipients}, Email not delievered to user "
                        f"{current_recipient['pk']} due to error: {exc.smtp_error}"
                    )
                    subtask_status.increment(failed=1)
                    failure_reason = f"SMTPDataError: {exc.smtp_error}"
                    subtask_status.add_failure_detail(email,failure_reason)

            except SINGLE_EMAIL_FAILURE_ERRORS as exc:
                # This will fall through and not retry the message.
                if exc.response['Error']['Code'] in ['MessageRejected', 'MailFromDomainNotVerified', 'MailFromDomainNotVerifiedException', 'FromEmailAddressNotVerifiedException']:   # lint-amnesty, pylint: disable=line-too-long
                    total_recipients_failed += 1
                    log.exception(
                        f"BulkEmail ==> Status: Failed(SINGLE_EMAIL_FAILURE_ERRORS), Task: {parent_task_id}, SubTask: "
                        f"{task_id}, EmailId: {email_id}, Recipient num: {recipient_num}/{total_recipients}, Recipient "
                        f"UserId: {current_recipient['pk']}"
                    )
                    subtask_status.increment(failed=1)
                    failure_reason = f"Single email failure: {exc}"
                    subtask_status.add_failure_detail(email, failure_reason)
                else:
                    raise exc

            else:
                total_recipients_successful += 1
                log.info(
                    f"BulkEmail ==> Status: Success, Task: {parent_task_id}, SubTask: {task_id}, EmailId: {email_id}, "
                    f"Recipient num: {recipient_num}/{total_recipients}, Recipient UserId: {current_recipient['pk']}"
                )
                if settings.BULK_EMAIL_LOG_SENT_EMAILS:
                    log.info(f"Email with id {email_id} sent to user {current_recipient['pk']}")
                else:
                    log.debug(f"Email with id {email_id} sent to user {current_recipient['pk']}")
                subtask_status.increment(succeeded=1)

            # Pop the user that was emailed off the end of the list only once they have
            # successfully been processed.  (That way, if there were a failure that
            # needed to be retried, the user is still on the list.)
            recipients_info[email] += 1
            to_list.pop()

        log.info(
            f"BulkEmail ==> Task: {parent_task_id}, SubTask: {task_id}, EmailId: {email_id}, Total Successful "
            f"Recipients: {total_recipients_successful}/{total_recipients}, Failed Recipients: "
            f"{total_recipients_failed}/{total_recipients}, Time Taken: {time.time() - start_time}"
        )

        duplicate_recipients = [f"{email} ({repetition})"
                                for email, repetition in recipients_info.most_common() if repetition > 1]
        if duplicate_recipients:
            log.info(
                f"BulkEmail ==> Task: {parent_task_id}, SubTask: {task_id}, EmailId: {email_id}, Total Duplicate "
                f"Recipients [{len(duplicate_recipients)}]"
            )

    except INFINITE_RETRY_ERRORS as exc:
        # Increment the "retried_nomax" counter, update other counters with progress to date,
        # and set the state to RETRY:
        if isinstance(exc, (SMTPDataError, SMTPSenderRefused)) or exc.response['Error']['Code'] in ['LimitExceededException']:   # lint-amnesty, pylint: disable=line-too-long
            subtask_status.increment(retried_nomax=1, state=RETRY)
            return _submit_for_retry(
                entry_id, email_id, to_list, global_email_context, exc, subtask_status, skip_retry_max=True
            )
        else:
            raise exc

    except LIMITED_RETRY_ERRORS as exc:
        # Errors caught here cause the email to be retried.  The entire task is actually retried
        # without popping the current recipient off of the existing list.
        # Errors caught are those that indicate a temporary condition that might succeed on retry.
        # Increment the "retried_withmax" counter, update other counters with progress to date,
        # and set the state to RETRY:

        subtask_status.increment(retried_withmax=1, state=RETRY)
        return _submit_for_retry(
            entry_id, email_id, to_list, global_email_context, exc, subtask_status, skip_retry_max=False
        )

    except BULK_EMAIL_FAILURE_ERRORS as exc:
        if isinstance(exc, SMTPException) or exc.response['Error']['Code'] in [
            'AccountSendingPausedException', 'MailFromDomainNotVerifiedException', 'LimitExceededException'
        ]:
            num_pending = len(to_list)
            log.exception(
                f"Task {task_id}: email with id {email_id} caused send_course_email "
                f"task to fail with 'fatal' exception. "
                f"{num_pending} emails unsent."
            )
            # Update counters with progress to date, counting unsent emails as failures,
            # and set the state to FAILURE:
            subtask_status.increment(failed=num_pending, state=FAILURE)
            return subtask_status, exc
        else:
            raise exc

    except Exception as exc:  # pylint: disable=broad-except
        # Errors caught here cause the email to be retried.  The entire task is actually retried
        # without popping the current recipient off of the existing list.
        # These are unexpected errors.  Since they might be due to a temporary condition that might
        # succeed on retry, we give them a retry.
        log.exception(
            f"Task {task_id}: email with id {email_id} caused send_course_email task to fail with unexpected "
            "exception. Generating retry."
        )
        # Increment the "retried_withmax" counter, update other counters with progress to date,
        # and set the state to RETRY:
        subtask_status.increment(retried_withmax=1, state=RETRY)
        return _submit_for_retry(
            entry_id, email_id, to_list, global_email_context, exc, subtask_status, skip_retry_max=False
        )

    else:
        # All went well.  Update counters with progress to date,
        # and set the state to SUCCESS:
        subtask_status.increment(state=SUCCESS)
        # Successful completion is marked by an exception value of None.
        return subtask_status, None
    finally:
        # Clean up at the end.
        connection.close()
