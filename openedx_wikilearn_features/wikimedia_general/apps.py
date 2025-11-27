"""
Wikimedia General App Config
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class WikimediaGeneralConfig(AppConfig):
    name = "openedx_wikilearn_features.wikimedia_general"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.CMS: {
                PluginURLs.NAMESPACE: "wikimedia_general",
                PluginURLs.REGEX: "^wikimedia_general/",
                PluginURLs.RELATIVE_PATH: "urls",
            },
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "wikimedia_general",
                PluginURLs.REGEX: "^wikimedia_general/",
                PluginURLs.RELATIVE_PATH: "urls",
            },
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }

    def ready(self):
        import openedx_wikilearn_features.wikimedia_general.signals  # pylint: disable=unused-import  # noqa: F401
        from openedx_wikilearn_features.wikimedia_general.utils import (
            load_core_patches,  # pylint: disable=import-outside-toplevel
        )

        load_core_patches()
