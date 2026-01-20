"""
Urls for Meta Translations v0 API(s)
"""
from django.urls import re_path

from openedx_wikilearn_features.meta_translations.api.v0.views import (
    ApproveAPIView,
    CouseBlockVersionUpdateView,
    GetCoursesVersionInfo,
    GetTranslationOutlineStructure,
    GetVerticalComponentContent,
    MetaCoursesListAPIView,
    MetaCoursesRetrieveAPIView,
    MetaCourseTranslationsAPIView,
    TranslatedVersionRetrieveAPIView,
)

app_name = 'translations_api_v0'

urlpatterns = [
    re_path(
        r'^outline/(?P<course_key>.+)$',
        GetTranslationOutlineStructure.as_view(),
        name='outline',
    ),
    re_path(
        r'^components/(?P<unit_key>.*?)$',
        GetVerticalComponentContent.as_view(),
        name='components',
    ),
    re_path(
        r'^versions$',
        GetCoursesVersionInfo.as_view(),
        name='versions',
    ),
    re_path(
        r'^approve_translations/$',
        ApproveAPIView.as_view(),
        name='approve-translations'
    ),
    re_path(
        r'^translated_versions/(?P<pk>\d+)/$',
        TranslatedVersionRetrieveAPIView.as_view(),
        name='translated_versions'
    ),
    re_path(
        r'^apply_translated_version/(?P<block_id>.*?)/$',
        CouseBlockVersionUpdateView.as_view(),
        name='course_block_version'
    ),
    re_path(
        r'^meta_courses/$',
        MetaCoursesListAPIView.as_view(),
        name='meta_courses'
    ),
    re_path(
        r'^meta_courses/(?P<course_id>.+)$',
        MetaCoursesRetrieveAPIView.as_view(),
        name='meta_course'
    ),
    re_path(
        r'^meta_course_translations/$',
        MetaCourseTranslationsAPIView.as_view(),
        name='meta_course_translations'
    ),
]
