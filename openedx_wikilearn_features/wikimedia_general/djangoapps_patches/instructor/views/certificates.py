"""
Custom issued-certificates report for the instructor dashboard's Data Download tab.

The stock ``get_issued_certificates`` report is a per-mode summary
(CourseID / Certificate Type / Total Certificates Issued / Date Report Run).
WikiLearn instead needs a per-learner report (Username / Grade /
Certificate Type / Certificate Creation Date / Certificate link), so the Data
Download template points the "Certificates Issued" buttons at this endpoint.

The response shape is identical to the stock view -- ``certificates`` /
``queried_features`` / ``feature_names`` for JSON, and a streamed CSV when
``?csv=true`` -- so the existing ``data_download.js`` front-end renders it
unchanged.
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.util.json_request import JsonResponse
from lms.djangoapps.certificates.data import CertificateStatuses
from lms.djangoapps.certificates.models import GeneratedCertificate
from lms.djangoapps.instructor import permissions
from lms.djangoapps.instructor_analytics import csvs as instructor_analytics_csvs
from openedx.core.lib.courses import get_course_by_id

log = logging.getLogger(__name__)
User = get_user_model()

# Column order and human-readable headers for the per-learner report.
QUERY_FEATURES = ['user', 'grade', 'mode', 'created_date', 'verify_uuid']
QUERY_FEATURE_NAMES = [
    ('user', _('Username')),
    ('grade', _('Grade')),
    ('mode', _('Certificate Type')),
    ('created_date', _('Certificate Creation Date')),
    ('verify_uuid', _('Certificate link')),
]


def _certificate_link(request, verify_uuid):
    """
    Return a fully-qualified certificate URL for ``verify_uuid``.

    Returns an empty string when the certificate has no ``verify_uuid``.
    """
    if not verify_uuid:
        return ''
    try:
        path = reverse('certificates:render_cert_by_uuid', kwargs={'certificate_uuid': verify_uuid})
    except NoReverseMatch:
        # Fall back to the well-known certificate path if the URL is not wired up.
        path = '/certificates/{}'.format(verify_uuid)
    return request.build_absolute_uri(path)


def _issued_certificates_data(request, course_key):
    """
    Build the per-learner issued-certificates rows for ``course_key``.

    Only downloadable (eligible) certificates are reported, mirroring the stock
    report. Usernames are resolved in a single query to avoid an N+1 lookup.
    """
    certificates = (
        GeneratedCertificate.eligible_certificates
        .filter(course_id=course_key, status=CertificateStatuses.downloadable)
        .values('user', 'grade', 'mode', 'created_date', 'verify_uuid')
        .order_by('created_date')
    )

    user_ids = {row['user'] for row in certificates if row['user']}
    usernames = dict(User.objects.filter(id__in=user_ids).values_list('id', 'username'))

    rows = []
    for row in certificates:
        rows.append({
            'user': usernames.get(row['user'], ''),
            'grade': row['grade'],
            'mode': row['mode'],
            'created_date': row['created_date'],
            'verify_uuid': _certificate_link(request, row['verify_uuid']),
        })
    return rows


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@transaction.non_atomic_requests
def get_issued_certificates(request, course_key_string):
    """
    Return the per-learner issued-certificates report for a course.

    ``POST`` (the "View Certificates Issued" button) returns JSON used to render
    the on-page table; ``GET`` with ``?csv=true`` streams the same data as a CSV.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden()

    try:
        course_key = CourseKey.from_string(course_key_string)
    except InvalidKeyError:
        raise Http404

    # get_course_by_id raises Http404 for unknown courses; guard everything else
    # so a transient lookup failure never 500s the instructor dashboard render.
    try:
        course = get_course_by_id(course_key)
    except Http404:
        raise
    except Exception:  # pylint: disable=broad-except
        log.exception('Unable to load course %s for issued certificates report', course_key_string)
        raise Http404

    if not request.user.has_perm(permissions.VIEW_ISSUED_CERTIFICATES, course):
        return HttpResponseForbidden()

    certificates_data = _issued_certificates_data(request, course_key)

    if request.GET.get('csv', 'false').lower() == 'true':
        __, data_rows = instructor_analytics_csvs.format_dictlist(certificates_data, QUERY_FEATURES)
        return instructor_analytics_csvs.create_csv_response(
            'issued_certificates.csv',
            [col_header for __, col_header in QUERY_FEATURE_NAMES],
            data_rows,
        )

    return JsonResponse({
        'certificates': certificates_data,
        'queried_features': QUERY_FEATURES,
        'feature_names': dict(QUERY_FEATURE_NAMES),
    })
