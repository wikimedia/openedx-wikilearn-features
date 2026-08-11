"""
Backfill the Wikilearn default course license onto courses that have none.
"""
from logging import getLogger

from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore

from openedx_wikilearn_features.wikimedia_general.tasks import (
    DEFAULT_COURSE_LICENSE,
    LICENSE_PRESERVED,
    LICENSE_SET,
    LICENSE_SKIPPED,
    apply_default_course_license,
)

LOGGER = getLogger(__name__)


class Command(BaseCommand):
    """
    Fill in the default course license on courses that do not have one.

    Courses whose license write was lost never got one: the inline write happened
    inside an open modulestore bulk operation, so the definition fork carrying it
    was discarded. This fills those blanks.

    Courses that already carry a license keep it, whatever it is. Those are
    reported at the end so they can be reviewed, because on an instance still
    running the old inline behaviour a non-default license is what makes a rerun
    fail.

    Usage:
        python manage.py cms backfill_course_licenses --dry-run
        python manage.py cms backfill_course_licenses
        python manage.py cms backfill_course_licenses --course course-v1:Org+Num+Run
    """

    help = "Set the default course license on courses that have no license of their own."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course",
            action="append",
            dest="courses",
            default=[],
            help="Course id to process. Repeatable. Defaults to every course.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        course_keys = self._resolve_course_keys(options["courses"])

        self.stdout.write(f"Default license: {DEFAULT_COURSE_LICENSE}")
        self.stdout.write(f"Courses to inspect: {len(course_keys)}{' (dry run)' if dry_run else ''}")

        counts = {LICENSE_SET: 0, LICENSE_PRESERVED: 0, LICENSE_SKIPPED: 0}
        non_default = []
        failed = []

        for course_key in course_keys:
            try:
                result = apply_default_course_license(course_key, dry_run=dry_run)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Failed to set default license for %s", course_key)
                failed.append((course_key, exc))
                continue

            counts[result] += 1
            if result == LICENSE_SET:
                self.stdout.write(f"  {'would set' if dry_run else 'set'}: {course_key}")
            elif result == LICENSE_SKIPPED:
                self.stdout.write(f"  skipped, course did not load: {course_key}")
            else:
                existing = self._existing_license(course_key)
                if existing != DEFAULT_COURSE_LICENSE:
                    non_default.append((course_key, existing))

        self.stdout.write(
            f"Done. set={counts[LICENSE_SET]} preserved={counts[LICENSE_PRESERVED]} "
            f"skipped={counts[LICENSE_SKIPPED]} failed={len(failed)}"
        )

        if non_default:
            self.stdout.write(f"Courses keeping a non-default license ({len(non_default)}):")
            for course_key, existing in non_default:
                self.stdout.write(f"  {course_key}: {existing}")

        for course_key, exc in failed:
            self.stdout.write(f"  failed: {course_key}: {exc}")

    def _existing_license(self, course_key):
        """
        Return the license currently on the course, for reporting only.
        """
        course = modulestore().get_course(course_key)
        return getattr(course, "license", None)

    def _resolve_course_keys(self, course_ids):
        """
        Return the course keys to process, from explicit ids or from every known course.
        """
        if not course_ids:
            return list(CourseOverview.objects.values_list("id", flat=True))

        course_keys = []
        for course_id in course_ids:
            try:
                course_keys.append(CourseKey.from_string(course_id))
            except InvalidKeyError as error:
                raise CommandError(f"Not a valid course id: {course_id}") from error
        return course_keys
