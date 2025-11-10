from logging import getLogger
from celery import shared_task
from celery_utils.logged_task import LoggedTask
from django.conf import settings
from django.contrib.auth.models import User

from openedx_wikilearn_features.email.utils import send_unread_messages_email

log = getLogger(__name__)


@shared_task(base=LoggedTask)
def send_unread_messages_email_task(data):
    for username, context in data.items():
        try:
            user = User.objects.get(username=username)
            send_unread_messages_email(user, context)
        except User.DoesNotExist:
            log.error(
                "Unable to send email User with username: {} does not exist.".format(settings.EMAIL_ADMIN)
            )
