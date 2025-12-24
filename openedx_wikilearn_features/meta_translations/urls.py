"""
Urls for Meta Translations
"""
from django.urls import include, re_path

from openedx_wikilearn_features.meta_translations.views import (
    course_blocks_api_send_fetch,
    course_blocks_mapping_view,
    render_discover_courses,
    render_translation_home,
    update_block_direction_flag,
)

app_name = 'meta_translations'

urlpatterns = [
    re_path(
        r'^course_blocks_mapping/$',
        course_blocks_mapping_view,
        name='course_blocks_mapping'
    ),
    re_path(
        r'^course_blocks_api_send_fetch/$',
        course_blocks_api_send_fetch,
        name='course_blocks_api_send_fetch'
    ),
    re_path(
        r'^direction/$',
        update_block_direction_flag,
        name='direction_flag'
    ),
    re_path(
        r'^$',
        render_translation_home,
        name='translations_home'
    ),
    re_path(
        r'^discover_courses/$',
        render_discover_courses,
        name='discover_courses'
    ),
    re_path(
        r'^discover_courses/(?P<course_key>.+)$',
        render_discover_courses,
        name='discover_course_translations'
    ),
    re_path(
        r'^api/v0/',
        include('openedx_wikilearn_features.meta_translations.api.v0.urls', namespace='translations_api_v0')
    ),
]
