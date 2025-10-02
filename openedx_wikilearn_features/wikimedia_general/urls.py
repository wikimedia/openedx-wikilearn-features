"""
URLs for the general features
"""

from django.urls import include, path

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
]
