
"""Production settings for Meta Translations"""

def plugin_settings(settings):
    """
    Production settings for Meta Translations
    """
    # Wiki Meta connection settings (WIKI_META_*) are provided per-environment by
    # the tutor-contrib-wikilearn plugin (openedx-cms-{development,production}-settings),
    # so they are no longer read from ENV_TOKENS here.
    settings.FETCH_CALL_DAYS_CONFIG_DEFAULT = settings.ENV_TOKENS.get('FETCH_CALL_DAYS_CONFIG_DEFAULT', settings.FETCH_CALL_DAYS_CONFIG_DEFAULT)
