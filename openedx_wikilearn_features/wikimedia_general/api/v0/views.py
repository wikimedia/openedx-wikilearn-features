"""
Views for wikimedia_general v0 API(s)
"""

from django.contrib.auth.decorators import login_required
from openedx.core.djangoapps.lang_pref.api import header_language_selector_is_enabled, released_languages
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from openedx_wikilearn_features.wikimedia_general.api.v0.utils import (
    get_authenticated_header_tabs,
    get_unauthenticated_header_tabs,
)


class RetrieveLMSTabs(generics.RetrieveAPIView):
    """
    API to get LMS tabs
    Response:
        {
            "tabs: [
                {
                    "id": String,
                    "name": String,
                    "url": URL
                },
                ...
            ]
        }
    """

    def get(self, request, *args, **kwargs):
        """
        Return header tabs for MFEs
        This API is particularly made for getting Authenticated header tabs
        """
        header_tabs = []
        if request.user.is_authenticated:
            header_tabs = get_authenticated_header_tabs(request.user)
        else:
            header_tabs = get_unauthenticated_header_tabs()

        return Response({"tabs": header_tabs}, status=status.HTTP_200_OK)


@api_view(["GET"])
@login_required
def get_released_languages(request):
    """
    An endpoint to enable language selector drop down in the MFEs.
    This is used to get the list of released languages.
    """
    response = {
        "released_languages": released_languages(),
    }
    return Response(response, status=status.HTTP_200_OK)


@api_view(["GET"])
@login_required
def get_language_selector_is_enabled(request):
    """
    Get whether the language selector is enabled or not.
    """
    language_selector_is_enabled = header_language_selector_is_enabled()
    response = {
        "language_selector_is_enabled": language_selector_is_enabled,
    }
    return Response(response, status=status.HTTP_200_OK)
