"""
Urls for Messenger
"""
from django.conf.urls import include
from django.urls import re_path

from  openedx_wikilearn_features.messenger.views import render_messenger_home

app_name = 'messenger'

urlpatterns = [
    re_path(
        r'^$',
        render_messenger_home,
        name='messenger_home'
    ),
    re_path(
        r'^api/v0/',
        include('openedx_wikilearn_features.messenger.api.v0.urls', namespace='messenger_api_v0')
    ),
]
