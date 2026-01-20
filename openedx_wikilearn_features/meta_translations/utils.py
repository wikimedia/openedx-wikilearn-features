"""
Files contains generic helping functions associated with meta_translations
"""

import json
from logging import getLogger

from django.utils.translation import gettext as _
from lms.djangoapps.courseware.courses import get_course_by_id
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangoapps.models.course_details import CourseDetails
from xmodule.modulestore.django import modulestore

from openedx_wikilearn_features.meta_translations.mapping.utils import course_blocks_mapping, get_recursive_blocks_data
from openedx_wikilearn_features.meta_translations.models import (
    CourseBlock,
    CourseTranslation,
    MetaTranslationConfiguration,
    TranslationVersion,
    WikiTranslation,
)

log = getLogger(__name__)


def get_children_block_ids(block_id, depth=4):
    """
    Get children_ids from a current block_location
    """
    block_location = UsageKey.from_string(block_id)
    block = modulestore().get_item(block_location)
    course_blocks = get_recursive_blocks_data(block, depth=depth, structured=False)
    return [UsageKey.from_string(course_block['usage_key']) for course_block in course_blocks]

def is_destination_block(block_id):
    """
    Get direction status
    """
    try:
        course_block = CourseBlock.objects.get(block_id=block_id)
        return course_block.is_destination()
    except CourseBlock.DoesNotExist:
        return False

def is_destination_course(course_id):
    """
    Check if the course is destination course i.e course is translated rerun
    """
    return CourseTranslation.objects.filter(course_id=course_id).exists()

def get_block_status(block_id):
    """
    Get data of course block
    {
        'mapped': True,
        'applied': True,
        'approved': True,
        'approved_by': username,
        'last_fetched': data,
    }
    """
    block_status = {}
    block_status['mapped'] = False
    try:
        course_block = CourseBlock.objects.get(block_id=block_id)
        block_info = course_block.get_block_info()
        if block_info:
            block_status = block_info
            block_status['mapped'] = True
    except CourseBlock.DoesNotExist:
        log.info('No CourseBlock found for block {}'.format(block_id))
    return block_status

def update_course_to_source(course_key):
    """
    Update course level flag from Destination to Source.
    It will also update all underlying blocks flag to source. Updating block-level flag to source means
    that it will not be tracked any more for translations. Any updated translations won't be fetched from wiki meta server.
    """
    try:
        translation_link = CourseTranslation.objects.get(course_id=course_key)
        log.info('Start converting course with id: {} to Source'.format(str(course_key)))
        # update all underlying component's flag to source
        course = get_course_by_id(course_key)
        log.info('Check and update all underlying blocks to Source'.format(str(course_key)))
        for course_block in CourseBlock.objects.filter(course_id=course_key):
            course_block.update_flag_to_source(course.language)
            log.info('Update course block with id: {} to Source'.format(str(course_key)))
        translation_link.delete()
        log.info('Course Flag with id: {} has been successfully updated to Source'.format(str(course_key)))
    except CourseTranslation.DoesNotExist:
        log.info('Course with id: {} is already a Source Course'.format(str(course_key)))

def reset_fetched_translation_and_version_history(base_course_block_data):
    """
    Reset translation and all versions from history
    """
    if base_course_block_data:
        for wiki_tarnslation in WikiTranslation.objects.filter(source_block_data=base_course_block_data).select_related("target_block"):
            wiki_tarnslation.translation = None
            wiki_tarnslation.approved = False
            wiki_tarnslation.save()

            target_block = wiki_tarnslation.target_block
            target_block.applied_version = None
            target_block.applied_translation = False
            target_block.translated = False
            target_block.save()

            TranslationVersion.objects.filter(block_id=target_block.block_id).delete()

def handle_base_course_block_deletion(usage_key):
    """
    Arguments:
        usage_key: deleted base course block.

    For given source block and all of it's children:
        - Disable translations for linked target blocks i.e update block direction flag to Source from Destination.
        - Delete Mapping i.e delete WikiTranslation entries for source block.
        - Set deleted flag to True on source CourseBlock

    Note:
        - We are setting deleted flag to True which will not allow any mapping creation in future i.e even
        if user clicks on mapping button, mapping for target blocks linked with particular deleted source
        blocks - won't be created.

        - We are not deleting CourseBlocks and CourseBlocksData from db and just updating language list
        and delete flag on CourseBlock because in next send call, meta server needs to be updated that
        translations for this base course block is not needed any more.
    """
    block_id = str(usage_key)
    children_ids = get_children_block_ids(block_id)
    log.info("Children ids for deletion: {}".format(children_ids))
    for child_block_id in children_ids:
        try:
            course_block = CourseBlock.objects.get(block_id=str(child_block_id))
            log.info("----> Start processing deletion of source block with block_id {}, block_type {}".format(
                course_block.block_id, course_block.block_type
            ))
            linked_target_blocks_mapping = WikiTranslation.objects.filter(source_block_data__course_block=course_block)
            log.info("Number of linked blocks found: {}".format(len(linked_target_blocks_mapping)))
            for mapping in linked_target_blocks_mapping:
                target_block = mapping.target_block
                target_language_code = get_course_by_id(target_block.course_id).language
                target_block.update_flag_to_source(target_language_code)
                mapping.delete()
            course_block.refresh_from_db()
            course_block.deleted = True
            course_block.save()
        except CourseBlock.DoesNotExist:
            log.info("Unable to find course block with block_id {}".format(str(child_block_id)))
            pass

def get_course_description_by_id(course_key):
    """
    Returns short course description of the course
    """
    return CourseDetails.fetch(course_key).short_description

def validate_translations(data, is_json = False):
    """
    Function that validates data of type display_name and content
    Returns:
        string: Empty if None else data
    """
    if is_json:
        return json.loads(data) if data else {}
    elif data == None:
        return ''
    return data

def validated_and_sort_translated_decodings(base_decodings, translated_decodings):
    """
    Validate and Sort Translated Decodings based on Base Decodings indexs
    Arguments:
        base_decodings: (dict) parsed decondings of base course block
        translated_decodings: (dict) new translations from meta server
    Returns:
        is_valid: (bool) check base_decodings and translated_decodings contain same keys and valid translated data
        sorted_translated_decodings: (dict) sorted dict based on base_decodings
    """
    sorted_translated_decodings = {}
    is_valid = True
    for key in base_decodings.keys():
        if translated_decodings.get(key) == None:
            is_valid = False
            sorted_translated_decodings[key] = ''
        else:
            sorted_translated_decodings[key] = translated_decodings[key]
    return is_valid, sorted_translated_decodings

def is_block_translated(block):
    """
    Returns True if the course block is translated
    """
    wiki_translations = block.wikitranslation_set.all()
    is_translated = bool(len(wiki_translations))
    for obj in wiki_translations:
        data_type = obj.source_block_data.data_type
        if WikiTranslation.is_translation_contains_parsed_keys(block.block_type, data_type):
            base_decodings = validate_translations(obj.source_block_data.parsed_keys)
            base_decodings = base_decodings if base_decodings else {}
            translated_decodings = validate_translations(obj.translation, is_json = True)
            is_valid, translated_decodings = validated_and_sort_translated_decodings(base_decodings, translated_decodings)
            is_translated = is_translated and is_valid
        else:
            translation = validate_translations(obj.translation)
            is_translated = is_translated and translation != ''
    return is_translated

def update_course_translations():
    """
    Update translation status of translated courses
    """
    transalted_courses = CourseTranslation.objects.filter().values_list('course_id', flat=True)
    course_blocks = CourseBlock.objects.filter(course_id__in=transalted_courses)
    updated_blocks = 0
    for block in course_blocks:
        is_translated = is_block_translated(block)
        if block.translated != is_translated:
            block.translated = is_translated
            updated_blocks+=1
            block.save()
    log.info('Updated Course Blocks: {}'.format(updated_blocks))

def get_studio_component_name(block_type):
    """
    Get block type names we see in studio i.e vertical -> unit, sequential -> subsection.
    """
    block_type_mapping = {
        "course": "course title",
        "chapter": "section",
        "sequential": "subsection",
        "vertical": "unit",
    }

    return block_type_mapping.get(block_type, block_type)

def get_show_meta_api_buttons(user):
    meta_config = MetaTranslationConfiguration.current()
    show_meta_api_buttons = False
    if meta_config and meta_config.enabled:
        if (user.is_staff and meta_config.staff_show_api_buttons) or meta_config.normal_users_show_api_buttons:
            # user is staff and config for staff is set otherwise check if config for normal users is set
            show_meta_api_buttons = True
    return show_meta_api_buttons

def validate_translated_rerun(is_translated_rerun, source_course_key, language):
    """
    Validate requirements for creating a translated rerun.

    Args:
        is_translated_rerun: Boolean indicating if this is a translated rerun
        source_course_key: The source course key string
        language: The target language for translation

    Returns:
        JsonResponse with error if validation fails, None if not a translated rerun or validation passes
    """
    from common.djangoapps.util.json_request import JsonResponse

    if not is_translated_rerun:
        return None  # Not a translated rerun, skip validation

    if not language:
        return JsonResponse({"ErrMsg": _("Course Language is required field for Translated rerun.")})

    if CourseTranslation.is_translated_rerun_exists_in_language(source_course_key, language):
        return JsonResponse(
            {"ErrMsg": _("Translated rerun for Source Course in selected language already exists.")}
        )

    source_course_details = CourseDetails.fetch(CourseKey.from_string(source_course_key))
    if not source_course_details or not source_course_details.language:
        return JsonResponse(
            {
                "ErrMsg": _(
                    "Translated rerun can not be created for the base course with no language. Please set base course language from settings."
                )
            },
        )

    return None  # Validation passed

def add_translation_metadata(xblock_info, xblock):
    """
    Add meta translation fields to the xBlockInfo in destination course only to show translation switch
    and a status of the block.
    
    Args:
        xblock_info: Dictionary containing xblock information
        xblock: The xblock object
        
    Returns:
        None (modifies xblock_info in place)
    """
    
    is_destination_course_block = is_destination_course(xblock.course_id)
    xblock_info['is_destination_course'] = is_destination_course_block

    if is_destination_course_block:
        xblock_info['meta_block_status'] = get_block_status(xblock.location)
        xblock_info['destination_flag'] = is_destination_block(xblock.location)
    
    if xblock.category == 'course':
        is_translated_or_base_course = CourseTranslation.is_base_or_translated_course(xblock.location.course_key)
        mapping_message = ''
        if is_translated_or_base_course == CourseTranslation._BASE_COURSE:
            mapping_message = 'Base-Course'
        elif is_translated_or_base_course == CourseTranslation._TRANSLATED_COURSE:
            mapping_message = 'Translated-Course'
        xblock_info['mapping_message'] = mapping_message

def rerun_course_translated(source_course_key, destination_course_key, user_id, is_translated_rerun, language):
    """
    Handle course translation setup if this is a translated rerun.
    """

    if is_translated_rerun:
        CourseTranslation.set_course_translation(destination_course_key, source_course_key)
        course_blocks_mapping(destination_course_key)
        
        if language:
            course_module = modulestore().get_course(destination_course_key)
            if course_module:
                course_module.language = language
                modulestore().update_item(course_module, user_id)

def get_translation_context(xblock):
    """
    Get translation-related context for the xblock template.
    
    Args:
        xblock: The xblock instance
        
    Returns:
        dict: Dictionary containing translation context fields
    """
    context = {}
    is_destination_course_block = is_destination_course(xblock.course_id)
    
    # Add meta translation fields as a reper fields in destination course containers
    # to show translation switch and a status of the block on header
    context['is_destination_course'] = is_destination_course_block
    
    if is_destination_course_block:
        context['meta_block_status'] = get_block_status(xblock.location)
        context['destination_flag'] = is_destination_block(xblock.location)
    
    return context
