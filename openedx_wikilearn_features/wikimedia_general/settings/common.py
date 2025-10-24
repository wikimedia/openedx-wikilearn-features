"""Settings"""


def plugin_settings(settings):
    """
    Required Common settings
    """
    settings.FEATURES["ENABLE_DEFAULT_COURSE_MODE_CREATION"] = False
    settings.BULK_EMAIL_DEFAULT_RETRY_DELAY = 60
    settings.BULK_EMAIL_MAX_RETRIES = 3
