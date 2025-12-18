from django.contrib import admin
from openedx.core.djangoapps.user_api.models import UserPreference

from openedx_wikilearn_features.wikimedia_general.models import Topic


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "key", "value")
    search_fields = ("user__username", "key", "value")
    list_filter = ("key",)
    ordering = ("user__username",)
    readonly_fields = ("user", "key", "value")
    exclude = ("id",)
    list_per_page = 100
    list_max_show_all = 100


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    list_per_page = 100
