"""
Views for wikimedia_general v0 API(s)
"""

from django.contrib.auth.decorators import login_required
from lms.djangoapps.courseware.courses import get_course_by_id
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.lang_pref.api import header_language_selector_is_enabled, released_languages
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from openedx_wikilearn_features.wikimedia_general.api.v0.utils import (
    get_authenticated_header_tabs,
    get_unauthenticated_header_tabs,
)

from .serializers import TopicSerializer


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


class RetrieveWikiMetaData(generics.RetrieveAPIView):
    """
    API to get course font
    Response:
        {
            "key": String,
            "course_font": String,

        }
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        course_key_string = kwargs.get('course_key_string')
        course_key = CourseKey.from_string(course_key_string)
        course = get_course_by_id(course_key)

        data = {
            'key': course_key_string,
            'course_font': course.course_font_family,
        }

        return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@login_required
def create_topic(request):
    """
    Create a new Topic.
    
    POST /api/v0/topics/
    Body: {"name": "Topic Name"}
    
    Returns:
        201: Topic created successfully
        400: Invalid data or topic already exists
    """
    serializer = TopicSerializer(data=request.data)
    
    if serializer.is_valid():
        serializer.save()
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )

