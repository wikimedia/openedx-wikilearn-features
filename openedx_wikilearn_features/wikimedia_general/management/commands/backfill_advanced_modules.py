"""
Backfill the Wikilearn default advanced XBlocks onto every existing course.

New courses get the default set of advanced_modules through the CourseOverview
post_save receiver in wikimedia_general.signals. This command does the same for
courses that already exist (anything created before the receiver was installed
or before a new module was added to DEFAULT_ADVANCED_MODULES).

It only ever appends — modules already listed on a course are preserved.
"""
from logging import getLogger

from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore

from openedx_wikilearn_features.wikimedia_general.signals import DEFAULT_ADVANCED_MODULES

LOGGER = getLogger(__name__)


class Command(BaseCommand):
    """
    Add any missing Wikilearn default advanced XBlocks to existing courses.

    Usage:
        python manage.py cms backfill_advanced_modules --dry-run
        python manage.py cms backfill_advanced_modules
        python manage.py cms backfill_advanced_modules --course course-v1:Org+Num+Run
    """

    help = "Append the Wikilearn default advanced XBlocks to every course that is missing one."

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

        self.stdout.write(f"Default advanced_modules: {list(DEFAULT_ADVANCED_MODULES)}")
        self.stdout.write(
            f"Courses to inspect: {len(course_keys)}{' (dry run)' if dry_run else ''}"
        )

        updated = 0
        unchanged = 0
        skipped = 0
        failed = []
        store = modulestore()

        for course_key in course_keys:
            try:
                course_block = store.get_course(course_key)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Could not load course %s", course_key)
                failed.append((course_key, exc))
                continue

            if course_block is None:
                skipped += 1
                self.stdout.write(f"  skipped, course did not load: {course_key}")
                continue

            existing = list(course_block.advanced_modules or [])
            to_add = [m for m in DEFAULT_ADVANCED_MODULES if m not in existing]
            if not to_add:
                unchanged += 1
                continue

            if dry_run:
                updated += 1
                self.stdout.write(f"  would add {to_add} to {course_key}")
                continue

            course_block.advanced_modules = existing + to_add
            try:
                store.update_item(course_block, ModuleStoreEnum.UserID.system)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Failed to update %s", course_key)
                failed.append((course_key, exc))
                continue

            updated += 1
            self.stdout.write(f"  added {to_add} to {course_key}")

        self.stdout.write(
            f"Done. updated={updated} unchanged={unchanged} skipped={skipped} failed={len(failed)}"
        )
        for course_key, exc in failed:
            self.stdout.write(f"  failed: {course_key}: {exc}")

    def _resolve_course_keys(self, course_ids):
        if not course_ids:
            return list(CourseOverview.objects.values_list("id", flat=True))

        course_keys = []
        for course_id in course_ids:
            try:
                course_keys.append(CourseKey.from_string(course_id))
            except InvalidKeyError as error:
                raise CommandError(f"Not a valid course id: {course_id}") from error
        return course_keys
