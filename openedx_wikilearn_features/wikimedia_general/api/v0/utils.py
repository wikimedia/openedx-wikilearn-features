"""
Wikimedia Helper functions
"""

from urllib.parse import urljoin

from common.djangoapps.edxmako.shortcuts import marketing_link
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _
from openedx.core.djangoapps.programs.models import ProgramsApiConfig


def get_unauthenticated_header_tabs():
    """
    Return header tabs for unauthenticated users
    """
    show_explore_courses = settings.FEATURES.get("COURSES_ARE_BROWSABLE")
    header_tabs = []

    if show_explore_courses:
        header_tabs.append(
            {
                "id": "catalog",
                "name": _("Catalog"),
                "url": urljoin(settings.LMS_ROOT_URL, marketing_link("COURSES")),
            }
        )

    return header_tabs


def get_authenticated_header_tabs(user):
    """
    Return header tabs for authenticated users
    """
    show_explore_courses = settings.FEATURES.get("COURSES_ARE_BROWSABLE")
    show_messenger_app = True
    programs_config = ProgramsApiConfig.current()

    header_tabs = [
        {
            "id": "courses",
            "name": _("Courses"),
            "url": urljoin(settings.LMS_ROOT_URL, reverse("dashboard")),
        },
    ]

    if programs_config.enabled:
        header_tabs.append(
            {
                "id": "programs",
                "name": _("Programs"),
                "url": urljoin(settings.LMS_ROOT_URL, reverse("program_listing_view")),
            }
        )

    if show_explore_courses:
        header_tabs.append(
            {
                "id": "catalog",
                "name": _("Catalog"),
                "url": urljoin(settings.LMS_ROOT_URL, marketing_link("COURSES")),
            }
        )

    if user.is_staff or user.is_superuser:
        header_tabs.append(
            {
                "id": "reports",
                "name": _("Reports"),
                "url": urljoin(settings.LMS_ROOT_URL, reverse("admin_dashboard:course_reports")),
            }
        )

    if show_messenger_app:
        header_tabs.append(
            {
                "id": "inbox",
                "name": _("Inbox"),
                "url": settings.MESSENGER_MICROFRONTEND_URL,
            }
        )

    # if user.is_superuser:
    #     header_tabs.append(
    #         {
    #             "id": "sysadmin",
    #             "name": _('Sysadmin'),
    #             "url": urljoin(settings.LMS_ROOT_URL, reverse('sysadmin:sysadmin')),
    #         }
    #     )
    return header_tabs
