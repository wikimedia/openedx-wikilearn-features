from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangolib.markup import HTML, Text
from common.djangoapps.util.json_request import JsonResponse
from lms.djangoapps.instructor.views.api import require_course_permission
from lms.djangoapps.instructor import permissions
from lms.djangoapps.instructor_task.models import ReportStore


@require_POST
@ensure_csrf_cookie
def list_report_downloads_student_admin(request, course_id):
    """
    List grade CSV files that are available for download for this course.
    """
    return _list_report_downloads_student_admin(request=request, course_id=course_id)


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_course_permission(permissions.CAN_RESEARCH)
def _list_report_downloads_student_admin(request, course_id):
    """
    List grade CSV files that are available for download for this course for student admins.
    Internal function with common code shared between DRF and functional views.
    """
    course_id = CourseKey.from_string(course_id)
    report_store = ReportStore.from_config(config_name="GRADES_DOWNLOAD")
    report_names = ["grade_report"]
    course_run = course_id.run # because filenames don't have course version

    response_payload = {"downloads": []}
    for name, url in report_store.links_for(course_id):
        if any(f"{course_run}_{report_name}" in name for report_name in report_names):
            response_payload["downloads"].append(
                dict(name=name, url=url, link=HTML('<a href="{}">{}</a>').format(HTML(url), Text(name)))
            )

    return JsonResponse(response_payload)
