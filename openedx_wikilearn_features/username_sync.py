"""
Keep WikiLearn usernames in sync with Wikimedia usernames, on every login.

Wikimedia accounts get renamed occasionally. Our social-auth ``uid`` is the
CentralAuth global user ID (``WikimediaIdentityServer.ID_KEY == "sub"``), which
survives a rename, so a renamed learner still lands in the right WikiLearn
account. What does not happen is the stored username being updated: social-auth
treats ``username`` as a protected field, and edx-platform's
``third_party_auth.pipeline.user_details_force_sync`` explicitly drops it from
the fields it is willing to sync. The learner is left displaying their old
Wikimedia name indefinitely.

This module closes that gap. ``sync_wikimedia_username`` is a social-auth
pipeline step that runs on every Wikimedia login and, when the reported name has
changed, hands off to ``rename_user`` -- which renames the account everywhere the
username is denormalised.

``rename_user`` is deliberately public: support can call it directly from a shell
for a one-off correction without going near the login flow.
"""

import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

log = logging.getLogger(__name__)

WIKIMEDIA_BACKEND_NAME = "wikimediaIdentityServer"

PIPELINE_STEP = "openedx_wikilearn_features.username_sync.sync_wikimedia_username"
PIPELINE_ANCHOR = "common.djangoapps.third_party_auth.pipeline.user_details_force_sync"

# Everywhere other than ``auth_user`` that a username is stored as a string rather
# than a foreign key, mirroring the canonical list in ``UsernameReplacementView``
# (openedx/core/djangoapps/user_api/accounts/views.py). Upstream keeps that list
# inline in a view method, so it cannot be imported. Models belonging to apps that
# are not installed on this deployment are skipped at runtime.
USERNAME_COLUMNS = (
    ("user_api.UserRetirementStatus", "original_username"),
    ("user_api.UserRetirementPartnerReportingStatus", "original_username"),
    ("consent.DataSharingConsent", "username"),
    ("consent.HistoricalDataSharingConsent", "username"),
    ("credit.CreditEligibility", "username"),
    ("credit.CreditRequest", "username"),
    ("credit.CreditRequirementStatus", "username"),
)

# Mirrors ``openedx.core.djangoapps.user_api.accounts.USERNAME_MAX_LENGTH``, kept
# local so this module stays importable outside of an LMS process.
DEFAULT_USERNAME_MAX_LENGTH = 30


def resolve_target_username(provider_username):
    """
    Normalise the username Wikimedia reported into the form the platform stores.

    The auth pipeline's ``get_username`` step truncates to ``USERNAME_MAX_LENGTH``
    when it first creates the account, so the same truncation has to be applied
    before comparing. Otherwise every learner whose Wikimedia name is longer than
    the limit looks permanently out of sync, and we would attempt -- and fail --
    to rename them on every single login.

    Arguments:
        provider_username (str): the raw ``username`` from the provider's profile.

    Returns:
        (str): the username as the platform would store it.
    """
    max_length = getattr(settings, "USERNAME_MAX_LENGTH", DEFAULT_USERNAME_MAX_LENGTH)
    return (provider_username or "").strip()[:max_length]


def _rename_blocked_reason(user, new_username):
    """
    Return why ``user`` must not be renamed to ``new_username``, or None if it can be.

    Arguments:
        user (User): the account to rename.
        new_username (str): the already-normalised target username.

    Returns:
        (str or None): a human-readable reason, suitable for logging.
    """
    from openedx.core.djangoapps.user_authn.views.registration_form import (  # pylint: disable=import-outside-toplevel
        validate_username,
    )

    if not new_username:
        return "Wikimedia reported an empty username"

    try:
        validate_username(new_username)
    except ValidationError as exc:
        return f"{new_username!r} is not a valid username here ({'; '.join(exc.messages)})"

    # Our MySQL collation is case-insensitive, so a learner who changed only the
    # capitalisation of their name would otherwise collide with their own row.
    if get_user_model().objects.filter(username=new_username).exclude(pk=user.pk).exists():
        return f"{new_username!r} already belongs to another account"

    return None


def rename_user(user, new_username):
    """
    Rename ``user`` to ``new_username`` everywhere the username is stored.

    Refuses rather than raises when the new name is unusable -- invalid, or held by
    somebody else -- because the caller is a login pipeline step that must carry on
    regardless. The reason is logged at WARNING so support can find it.

    Arguments:
        user (User): the account to rename. Its in-memory ``username`` is updated
            on success, so later pipeline steps see the new value.
        new_username (str): the target username, already passed through
            ``resolve_target_username``.

    Returns:
        (bool): True if the rename happened.
    """
    if new_username == user.username:
        return False

    reason = _rename_blocked_reason(user, new_username)
    if reason:
        log.warning(
            "[username_sync] Not renaming user_id=%s from %r: %s",
            user.id,
            user.username,
            reason,
        )
        return False

    old_username = user.username
    with transaction.atomic():
        # ``update()`` rather than ``save()``, so no User post_save receiver fires
        # for what is only a relabelling. The in-memory object is corrected below
        # so the rest of the login pipeline -- notably the JWT written by
        # ``set_logged_in_cookies`` -- carries the new username.
        get_user_model().objects.filter(pk=user.pk).update(username=new_username)
        for label, column in USERNAME_COLUMNS:
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            model.objects.filter(**{column: old_username}).update(**{column: new_username})
    user.username = new_username

    log.info(
        "[username_sync] Renamed user_id=%s from %r to %r",
        user.id,
        old_username,
        new_username,
    )
    _rename_in_forum(user, new_username)
    return True


def _rename_in_forum(user, new_username):
    """
    Push the new username into the forums.

    The forums keep their own copy of the username on the user document and
    denormalise it onto every thread and comment as ``author_username``, so this
    has to happen or the learner's back catalogue keeps their old name.

    Deliberately outside the transaction above: the forum store is not part of it,
    and a forum failure must not undo the rename. The LMS row is the source of
    truth and the forums can always be re-synced.

    Arguments:
        user (User): the already-renamed account.
        new_username (str): the new username.
    """
    from openedx.core.djangoapps.django_comment_common import (  # pylint: disable=import-outside-toplevel
        comment_client,
    )

    try:
        comment_client.User.from_django_user(user).replace_username(new_username)
    except Exception:  # pylint: disable=broad-except
        # Usually just means the learner has never posted and so has no forum
        # profile. Anything else is worth seeing, but not worth failing over.
        log.exception("[username_sync] Could not rename user_id=%s in the forums", user.id)


def sync_wikimedia_username(backend=None, details=None, user=None, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Social-auth pipeline step: make the WikiLearn username match Wikimedia's.

    Runs on every Wikimedia login. When nothing has changed -- the overwhelmingly
    common case -- it costs one string comparison and touches no database.
    """
    if user is None or backend is None or backend.name != WIKIMEDIA_BACKEND_NAME:
        return

    target = resolve_target_username((details or {}).get("username"))
    if not target or target == user.username:
        return

    try:
        rename_user(user, target)
    except Exception:  # pylint: disable=broad-except
        # Keeping a display name tidy must never cost a learner their login.
        log.exception("[username_sync] Rename failed for user_id=%s during login", user.id)


def install_pipeline_step():
    """
    Insert ``sync_wikimedia_username`` into ``SOCIAL_AUTH_PIPELINE``.

    This has to run from ``AppConfig.ready`` rather than from plugin settings:
    ``third_party_auth``'s own ``ready()`` assigns ``SOCIAL_AUTH_PIPELINE``
    wholesale (see ``common/djangoapps/third_party_auth/settings.py``), so
    anything set while settings are still loading is overwritten. Plugin apps are
    appended to ``INSTALLED_APPS`` after the core apps, so our ``ready()`` runs
    after theirs and wins.

    Safe to call from CMS, or with third-party auth disabled, where there is no
    pipeline to extend.
    """
    pipeline = list(getattr(settings, "SOCIAL_AUTH_PIPELINE", None) or [])
    if not pipeline or PIPELINE_STEP in pipeline:
        return

    if PIPELINE_ANCHOR in pipeline:
        # Immediately after the provider's profile data is synced, and before the
        # login cookies are written, so the JWT carries the new username.
        pipeline.insert(pipeline.index(PIPELINE_ANCHOR) + 1, PIPELINE_STEP)
    else:
        log.warning(
            "[username_sync] %s missing from SOCIAL_AUTH_PIPELINE; appending %s to the end instead",
            PIPELINE_ANCHOR,
            PIPELINE_STEP,
        )
        pipeline.append(PIPELINE_STEP)

    settings.SOCIAL_AUTH_PIPELINE = pipeline
