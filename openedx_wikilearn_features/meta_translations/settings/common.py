
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
    # Fetch call throttling. Meta rate-limits at the CDN edge per source IP; exceeding it
    # returns a 429 HTML page for every subsequent request. SYNC_LIMIT requests are sent
    # concurrently, then the job sleeps GET_REQUEST_DELAY seconds before the next batch,
    # giving a ceiling of SYNC_LIMIT/GET_REQUEST_DELAY requests per second.
    settings.WIKI_META_API_GET_REQUEST_SYNC_LIMIT = 2
    settings.WIKI_META_API_GET_REQUEST_DELAY_IN_SECONDS = 1
    # Per-request retries when Meta answers 429, backing off between attempts.
    settings.WIKI_META_API_MAX_RETRIES = 3
    # Abort the fetch run after this many consecutive fully-failed batches, rather than
    # spending the rest of the run hammering a service that asked us to slow down.
    settings.WIKI_META_API_MAX_CONSECUTIVE_FAILED_BATCHES = 5
    settings.FETCH_CALL_DAYS_CONFIG_DEFAULT = 3
