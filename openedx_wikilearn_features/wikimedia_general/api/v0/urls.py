"""
Urls for Messenger v0 API(s)
"""

from django.urls import re_path

from openedx_wikilearn_features.wikimedia_general.api.v0.views import RetrieveLMSTabs

app_name = "general_api_v0"

urlpatterns = [
    re_path(r"lms_tabs", RetrieveLMSTabs.as_view(), name="retrieve_lms_tabs"),
]
