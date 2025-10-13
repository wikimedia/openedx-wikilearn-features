"""
Urls for Messenger
"""
from django.conf.urls import include
from django.urls import re_path


app_name = 'messenger'

urlpatterns = [
    re_path(
        r'^api/v0/',
        include('openedx_wikilearn_features.messenger.api.v0.urls', namespace='messenger_api_v0')
    ),
]
