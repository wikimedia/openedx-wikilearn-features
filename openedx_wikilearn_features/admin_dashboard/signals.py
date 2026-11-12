from celery.states import SUCCESS
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext as _
from django.utils.translation import ngettext, override
from lms.djangoapps.instructor_task.models import InstructorTask
from opaque_keys import InvalidKeyError
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
from openedx.core.djangoapps.user_api.models import UserPreference

from openedx_wikilearn_features.admin_dashboard.models import AdminReportTask
from openedx_wikilearn_features.admin_dashboard.tasks import (
    send_report_ready_email_task,
)
from openedx_wikilearn_features.admin_dashboard.utils import get_report_tab_link, get_instructor_tab_link


def send_report_ready_email(instance, report_link):
    """Send email to the user who requesed the report

    Args:
        instance ( AdminReportTask | InstructorTask ): instance of the report task being saved
    """
    email = instance.requester.email
    report_type = instance.task_type.replace("_", " ").title()

    if isinstance(instance.course_id, str):
        course_ids = instance.course_id.split(",")
    else:
        course_ids = [str(instance.course_id)]

    try:
        courses = list(CourseOverview.objects.filter(id__in=course_ids))
    except InvalidKeyError:
        courses = []

    language = UserPreference.get_value(instance.requester, LANGUAGE_KEY) or settings.LANGUAGE_CODE

    # This runs outside a request, so no language is active; translate eagerly because the
    # message is passed to Celery.
    with override(language):
        if courses:
            course_names = ", ".join(f'"{course.display_name}"' for course in courses)
            email_msg = ngettext(
                'The "{report_type}" report you requested for the course {course_names} is ready.',
                'The "{report_type}" report you requested for the courses {course_names} is ready.',
                len(courses),
            ).format(report_type=report_type, course_names=course_names)
        else:
            email_msg = _('The "{report_type}" report you requested for all courses is ready.').format(
                report_type=report_type
            )

    data = {"report_link": report_link, "email_msg": email_msg}
    send_report_ready_email_task.delay("report_ready", data, "", [email], language)


@receiver(post_save, sender=AdminReportTask)
def send_email_when_report_ready(sender, instance, created, **kwargs):
    if instance.task_state == SUCCESS:
        send_report_ready_email(instance, get_report_tab_link())


@receiver(post_save, sender=InstructorTask)
def send_email_when_report_ready_instructor(sender, instance, created, **kwargs):
    admin_report_task_types = [
        "generate_anonymous_ids_for_course",
        "profile_info_csv",
        "grade_course",
        "grade_problems",
    ]

    if instance.task_state == SUCCESS and instance.task_type in admin_report_task_types:
        send_report_ready_email(instance, get_instructor_tab_link(instance.course_id))
