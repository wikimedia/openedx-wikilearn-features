"""
Urls for Messenger v0 API(s)
"""
from django.urls import re_path

from openedx_wikilearn_features.messenger.api.v0.views import (
    InboxView, ConversationView, MessageCreateView, UserSearchView, BulkMessageView
)

app_name = 'messenger_api_v0'


urlpatterns = [
    re_path(
        r'^bulk_message/$',
        BulkMessageView.as_view({
            'post': 'bulk_message'
        }),
        name="bulk_message"
    ),
    re_path(
        r'^user/$',
        UserSearchView.as_view({
            'get': 'list'
        }),
        name="user_search"
    ),
    re_path(
        r'^inbox/$',
        InboxView.as_view({
            'get': 'list'
        }),
        name="user_inbox_list"
    ),
    re_path(
        r'^inbox/(?P<pk>\d+)/$',
        InboxView.as_view({
            'patch': 'partial_update',
            'get': 'retrieve'
        }),
        name="user_inbox_detail"
    ),
    re_path(
        r'^conversation/$',
        ConversationView.as_view({
            'get': 'list',
        }),
        name="conversation_list"
    ),
    re_path(
        r'^message/$',
        MessageCreateView.as_view(),
        name="message_create"
    ),
]
