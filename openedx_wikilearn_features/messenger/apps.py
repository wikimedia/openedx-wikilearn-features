"""
Messenger App Config
"""
from django.apps import AppConfig
from django.conf import settings
import os

from edx_django_utils.plugins import PluginURLs, PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class MessengerConfig(AppConfig):
    name = 'openedx_wikilearn_features.messenger'

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: 'messenger',
                PluginURLs.REGEX: '^messenger/',
                PluginURLs.RELATIVE_PATH: 'urls',
            }
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: 'settings.common'},
            }
        }
    }

    def ready(self):
        from . import signals  # pylint: disable=unused-import
