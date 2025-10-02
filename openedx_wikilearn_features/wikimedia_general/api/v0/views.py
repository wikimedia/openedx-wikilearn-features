"""
Views for wikimedia_general v0 API(s)
"""

from rest_framework import generics, status
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
