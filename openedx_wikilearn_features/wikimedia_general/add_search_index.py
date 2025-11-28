"""
Patches for courseware_index to add custom search index fields.
"""
import logging
import os

from django.conf import settings

log = logging.getLogger(__name__)


def patch_courseware_index():
    """
    Patch AboutInfo class and CourseAboutSearchIndexer to add custom search index fields.
    This should only be called when running in CMS context.
    """
    # Lazy imports to avoid circular import issues
    from cms.djangoapps.contentstore.courseware_index import AboutInfo, CourseAboutSearchIndexer

    from openedx_wikilearn_features.wikimedia_general.utils import get_pace_type
    
    # Define the new methods
    def from_pace_type(self, **kwargs):
        """Extracts the self_paced value from course and returns PacedType."""
        course = kwargs.get('course', None)
        if not course:
            raise ValueError("Context dictionary does not contain expected argument 'course'")
        
        self_paced = getattr(course, 'self_paced', None)
        return get_pace_type(self_paced)
    
    def from_course_other_settings(self, **kwargs):
        """gets the value from the course_other_settings object"""
        course = kwargs.get('course', None)
        if not course:
            raise ValueError("Context dictionary does not contain expected argument 'course'")
        
        other_course_settings = getattr(course, 'other_course_settings', None)
        if not other_course_settings:
            log.warning("Course object does not contain expected argument 'other_course_settings'")
            return None
        # Will return None if not found
        # For some reason, getattr() doesn't work on other_course_settings
        setting = other_course_settings.get(self.property_name)
        return setting
    
    # Add methods to AboutInfo class
    AboutInfo.from_pace_type = from_pace_type
    AboutInfo.from_course_other_settings = from_course_other_settings
    
    # Add class attributes
    AboutInfo.FROM_PACE_TYPE = from_pace_type
    AboutInfo.FROM_COURSE_OTHER_SETTINGS = from_course_other_settings
    
    # Add to the indexer if not already present
    if not any(info.property_name == "pace_type" for info in CourseAboutSearchIndexer.ABOUT_INFORMATION_TO_INCLUDE):
        CourseAboutSearchIndexer.ABOUT_INFORMATION_TO_INCLUDE.append(
            AboutInfo("pace_type", AboutInfo.PROPERTY, AboutInfo.FROM_PACE_TYPE)
        )
    if not any(info.property_name == "topic" for info in CourseAboutSearchIndexer.ABOUT_INFORMATION_TO_INCLUDE):
        CourseAboutSearchIndexer.ABOUT_INFORMATION_TO_INCLUDE.append(
            AboutInfo("topic", AboutInfo.PROPERTY, AboutInfo.FROM_COURSE_OTHER_SETTINGS)
        )

    log.info("Successfully patched courseware_index for pace_type and topic indexing")

def load_search_index_patches():
    # Check if we're running CMS
    service_variant = os.environ.get('SERVICE_VARIANT', '')
    is_cms = service_variant == 'cms' or 'cms' in settings.INSTALLED_APPS
    
    if is_cms:
        patch_courseware_index()
