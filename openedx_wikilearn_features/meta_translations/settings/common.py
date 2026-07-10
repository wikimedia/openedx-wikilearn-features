
"""Common settings for Meta Translations"""
from pathlib import Path

import openedx_wikilearn_features.meta_translations
from openedx_wikilearn_features.meta_translations.transformers.wiki_transformer import (
    ProblemTransformer,
    VideoTranscriptTransformer,
)

META_TRANSLATIONS_ROOT = Path(openedx_wikilearn_features.meta_translations.__file__).parent


def plugin_settings(settings):
    """
    Common settings for Meta Translations
    """
    settings.MAKO_TEMPLATE_DIRS_BASE.append(
      META_TRANSLATIONS_ROOT / 'templates',
    )

    settings.STATICFILES_DIRS.append(
      META_TRANSLATIONS_ROOT / 'static',
    )

    # settings for wiki_transformers
    settings.DATA_TYPES_WITH_PARCED_KEYS = ['content', 'transcript']
    settings.TRANSFORMER_CLASS_MAPPING = {
        'problem': ProblemTransformer,
        'video': VideoTranscriptTransformer,
    }
    settings.ACCEPTED_PROBLEM_XML_TAGS = [
      'choiceresponse',
      'optionresponse',
      'multiplechoiceresponse',
      'numericalresponse',
      'stringresponse',
    ]

    # Wiki Meta connection settings (base/api URLs, content model, mcgroup &
    # course prefixes, API username/password) are set per-environment by the
    # tutor-contrib-wikilearn plugin via the openedx-cms-development-settings /
    # openedx-cms-production-settings patches. Only the non-environment-specific
    # operational defaults live here.
    settings.WIKI_META_API_REQUEST_DELAY_IN_SECONDS = 20
    settings.WIKI_META_API_GET_REQUEST_SYNC_LIMIT = 3
    settings.FETCH_CALL_DAYS_CONFIG_DEFAULT = 3
