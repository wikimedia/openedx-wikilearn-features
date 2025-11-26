"""
Urls for Messenger v0 API(s)
"""

from django.urls import re_path

from openedx_wikilearn_features.wikimedia_general.api.v0.views import (
    RetrieveLMSTabs,
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
]
