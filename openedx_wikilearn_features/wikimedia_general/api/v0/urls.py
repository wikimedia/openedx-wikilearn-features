"""
Urls for Messenger v0 API(s)
"""

from django.conf import settings
from django.urls import re_path

from openedx_wikilearn_features.wikimedia_general.api.v0.views import (
    RetrieveLMSTabs,
    RetrieveWikiMetaData,
    create_topic,
    get_issued_certificates,
    get_language_selector_is_enabled,
    get_released_languages,
)

app_name = "general_api_v0"

urlpatterns = [
    re_path(r"lms_tabs", RetrieveLMSTabs.as_view(), name="retrieve_lms_tabs"),
    re_path(r"released_languages", get_released_languages, name="released_languages"),
    re_path(
        r"language_selector_is_enabled",
        get_language_selector_is_enabled,
        name="language_selector_is_enabled",
    ),
    re_path(
        rf"^wiki_metadata/{settings.COURSE_KEY_PATTERN}",
        RetrieveWikiMetaData.as_view(),
        name="course_font",
    ),
    re_path(r"topics", create_topic, name="create_topic"),
    re_path(
        rf"^get_issued_certificates/{settings.COURSE_KEY_PATTERN}",
        get_issued_certificates,
        name="get_issued_certificates",
    ),
]
