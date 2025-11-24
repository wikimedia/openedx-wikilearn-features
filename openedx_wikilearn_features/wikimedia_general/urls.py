"""
URLs for the general features
"""

from django.urls import include, path
from openedx_wikilearn_features.wikimedia_general.djangoapps_patches.instructor.views.utils import (
    list_report_downloads_student_admin,
)
app_name = "wikimedia_general"

urlpatterns = [
    path(
        "api/v0/",
        include(
            (
                "openedx_wikilearn_features.wikimedia_general.api.v0.urls",
                "general_api_v0",
            )
        ),
    ),
    path('<course_id>/list_report_downloads_student_admin/',
         list_report_downloads_student_admin, name='list_report_downloads_student_admin'),
]
