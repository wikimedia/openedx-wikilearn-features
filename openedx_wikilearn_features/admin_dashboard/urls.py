"""
Urls for Admin Dashboard
"""

from django.conf import settings
from django.urls import path, re_path

from openedx_wikilearn_features.admin_dashboard.admin_task.api import (
    all_courses_enrollment_report,
    average_calculate_grades_csv,
    course_version_report,
    courses_enrollment_report,
    enrollment_activity_report,
    list_all_courses_report_downloads,
    pending_tasks,
    progress_report_csv,
    user_pref_lang_report,
    users_enrollment_report,
)
from openedx_wikilearn_features.admin_dashboard.course_reports import course_reports

app_name = "admin_dashboard"
urlpatterns = [
    re_path(
        r"^average_calculate_grades_csv/{}$".format(
            settings.COURSE_ID_PATTERN,
        ),
        average_calculate_grades_csv,
        name="average_calculate_grades_csv",
    ),
    re_path(
        r"^progress_report_csv/{}$".format(
            settings.COURSE_ID_PATTERN,
        ),
        progress_report_csv,
        name="progress_report_csv",
    ),
    re_path(
        r"^course_version_report/{}$".format(
            settings.COURSE_ID_PATTERN,
        ),
        course_version_report,
        name="course_version_report",
    ),
    re_path(
        r"^courses_enrollment_report",
        courses_enrollment_report,
        name="courses_enrollment_report",
    ),
    re_path(
        r"^all_courses_enrollment_report",
        all_courses_enrollment_report,
        name="all_courses_enrollment_report",
    ),
    re_path(r"^user_pref_lang_report", user_pref_lang_report, name="user_pref_lang_report"),
    re_path(
        r"^users_enrollment_report",
        users_enrollment_report,
        name="users_enrollment_report",
    ),
    re_path(
        r"^enrollment_activity_report",
        enrollment_activity_report,
        name="enrollment_activity_report",
    ),
    path(
        "list_all_courses_report_downloads",
        list_all_courses_report_downloads,
        name="list_all_courses_report_downloads",
    ),
    path("pending_tasks/<str:course_id>", pending_tasks, name="pending_tasks"),
    re_path(r"", course_reports, name="course_reports"),
]
