from logging import getLogger

from django.core.management.base import BaseCommand
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.discussions.models import DiscussionsConfiguration
from openedx.core.djangoapps.discussions.serializers import DiscussionsConfigurationSerializer
from openedx.core.lib.api.view_utils import validate_course_key

log = getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to sync discussion configurations for all courses.

    python manage.py sync_discussions_configuration

    For each course, it fetches the current discussion configuration via the serializer
    and then re-saves it with the same data, without any modifications.
    This is used for synchronization purposes only.
    """

    help = "Syncs discussion configurations for all courses"

    def handle(self, *args, **options):
        all_courses = CourseOverview.get_all_courses()

        log.info("Starting discussion configuration sync for all courses...")

        success_count = 0
        failure_count = 0

        for course in all_courses:
            course_key_string = str(course.id)
            log.info(f"Processing course: {course_key_string}")

            try:
                course_key = validate_course_key(course_key_string)
                configuration = DiscussionsConfiguration.get(course_key)

                # GET: serialize current configuration
                serializer = DiscussionsConfigurationSerializer(
                    configuration,
                    context={'user_id': None, 'provider_type': 'openedx'},
                )
                data = serializer.data

                # POST: re-save the same data back
                serializer = DiscussionsConfigurationSerializer(
                    configuration,
                    context={'user_id': None},
                    data=data,
                    partial=True,
                )
                if serializer.is_valid(raise_exception=True):
                    serializer.save()

                log.info(f"Successfully synced configuration for course: {course_key_string}")
                success_count += 1

            except Exception as e:
                log.exception(f"Failed to sync configuration for course {course_key_string}: {e}")
                failure_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete. Success: {success_count}, Failed: {failure_count}"
            )
        )
