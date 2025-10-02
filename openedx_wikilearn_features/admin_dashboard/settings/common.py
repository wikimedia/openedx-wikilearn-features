"""
Common settings for Admin Dashboard
"""

from openedx_wikilearn_features import ROOT_DIRECTORY


def plugin_settings(settings):
    settings.MAKO_TEMPLATE_DIRS_BASE.append(ROOT_DIRECTORY / "admin_dashboard" / "templates")
