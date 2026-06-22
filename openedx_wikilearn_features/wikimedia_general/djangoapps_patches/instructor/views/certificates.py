"""
Per-learner issued-certificates report for the instructor dashboard "Data Download".

Replaces the stock per-course aggregate view, whose "Certificate link" column is
always empty because it reads the deprecated ``download_url`` PDF field. Reports:

    Username / Grade / Certificate Type / Certificate Creation Date / Certificate link

Wired in under the existing ``get_issued_certificates`` URL name, so the dashboard
buttons work with no frontend changes.
"""

from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from opaque_keys.edx.keys import CourseKey

from common.djangoapps.util.json_request import JsonResponse
from lms.djangoapps.certificates.api import get_certificate_url
from lms.djangoapps.certificates.data import CertificateStatuses
from lms.djangoapps.certificates.models import GeneratedCertificate
from lms.djangoapps.instructor import permissions
from lms.djangoapps.instructor.views.api import require_course_permission
from lms.djangoapps.instructor_analytics import csvs as instructor_analytics_csvs


@ensure_csrf_cookie
@require_course_permission(permissions.VIEW_ISSUED_CERTIFICATES)
def get_issued_certificates(request, course_id):
    """
    Return the per-learner issued-certificates report for ``course_id``.

    Responds with JSON for the table, or a CSV download when ``?csv=true`` is passed.
    """
    course_key = CourseKey.from_string(course_id)
    csv_required = request.GET.get('csv', 'false')

    query_features = ['username', 'grade', 'mode', 'created_date', 'certificate_link']
    query_features_names = [
        ('username', _('Username')),
        ('grade', _('Grade')),
        ('mode', _('Certificate Type')),
        ('created_date', _('Certificate Creation Date')),
        ('certificate_link', _('Certificate link')),
    ]

    certificates_data = _issued_certificates(request, course_key)

    if csv_required.lower() == 'true':
        __, data_rows = instructor_analytics_csvs.format_dictlist(certificates_data, query_features)
        return instructor_analytics_csvs.create_csv_response(
            'issued_certificates.csv',
            [col_header for __, col_header in query_features_names],
            data_rows,
        )

    return JsonResponse({
        'certificates': certificates_data,
        'queried_features': query_features,
        'feature_names': dict(query_features_names),
    })


def _issued_certificates(request, course_key):
    """Build the list of issued-certificate dicts for ``course_key``."""
    # Only downloadable certs, matching the set the stock aggregate report counts.
    certificates = GeneratedCertificate.eligible_certificates.filter(
        course_id=course_key,
        status=CertificateStatuses.downloadable,
    ).select_related('user').order_by('user__username')

    certificates_data = []
    for certificate in certificates:
        # Returns a site-relative path; make it absolute for table and CSV use.
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