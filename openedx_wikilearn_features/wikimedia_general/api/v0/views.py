"""
Views for wikimedia_general v0 API(s)
"""

from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from lms.djangoapps.certificates.api import get_certificate_url
from lms.djangoapps.certificates.data import CertificateStatuses
from lms.djangoapps.certificates.models import GeneratedCertificate
from lms.djangoapps.courseware.courses import get_course_by_id
from lms.djangoapps.instructor import permissions as instructor_permissions
from lms.djangoapps.instructor_analytics import csvs as instructor_analytics_csvs
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


@api_view(['GET', 'POST'])
@login_required
def get_issued_certificates(request, course_key_string):
    """
    Per-learner issued-certificates report for the instructor dashboard "Data Download".

    Replaces the stock per-course aggregate report (whose "Certificate link" column is
    always empty because it reads the deprecated ``download_url`` PDF field) with:

        Username / Grade / Certificate Type / Certificate Creation Date / Certificate link

    Responds with JSON for the dashboard table, or a CSV download when ``?csv=true`` is
    passed. Gated by the same ``instructor.view_issued_certificates`` permission as the
    stock endpoint.
    """
    course_key = CourseKey.from_string(course_key_string)
    course = get_course_by_id(course_key)
    if not request.user.has_perm(instructor_permissions.VIEW_ISSUED_CERTIFICATES, course):
        return Response(status=status.HTTP_403_FORBIDDEN)

    query_features = ['username', 'grade', 'mode', 'created_date', 'certificate_link']
    query_features_names = [
        ('username', _('Username')),
        ('grade', _('Grade')),
        ('mode', _('Certificate Type')),
        ('created_date', _('Certificate Creation Date')),
        ('certificate_link', _('Certificate link')),
    ]

    certificates_data = _issued_certificates(request, course_key)

    if request.GET.get('csv', 'false').lower() == 'true':
        __, data_rows = instructor_analytics_csvs.format_dictlist(certificates_data, query_features)
        return instructor_analytics_csvs.create_csv_response(
            'issued_certificates.csv',
            [col_header for __, col_header in query_features_names],
            data_rows,
        )

    return Response({
        'certificates': certificates_data,
        'queried_features': query_features,
        'feature_names': dict(query_features_names),
    })


def _issued_certificates(request, course_key):
    """
    Build the per-learner issued-certificate rows for ``course_key``.

    Only downloadable (i.e. actually issued) certificates are included, matching the
    set the stock aggregate report counts.
    """
    certificates = GeneratedCertificate.eligible_certificates.filter(
        course_id=course_key,
        status=CertificateStatuses.downloadable,
    ).select_related('user').order_by('user__username')

    certificates_data = []
    for certificate in certificates:
        # ``get_certificate_url`` returns a site-relative path; make it absolute so the
        # link is usable in both the table and the exported CSV. May be empty when the
        # course has no resolvable certificate URL, in which case leave it blank.
        certificate_url = get_certificate_url(
            user_id=certificate.user_id,
            course_id=course_key,
            uuid=certificate.verify_uuid,
        )
        certificates_data.append({
            'username': certificate.user.username,
            'grade': certificate.grade,
            'mode': certificate.mode,
            'created_date': certificate.created_date.strftime('%B %d, %Y'),
            'certificate_link': request.build_absolute_uri(certificate_url) if certificate_url else '',
        })

    return certificates_data

