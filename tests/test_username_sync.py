"""
Tests for the `username_sync` module.

Covers the parts that do not need a running LMS: username normalisation, pipeline
installation, and every guard clause on the pipeline step. `rename_user` itself
writes to platform models and is exercised against a real deployment rather than
this standalone harness.
"""

from unittest import mock

import pytest
from django.test import override_settings

from openedx_wikilearn_features.username_sync import (
    PIPELINE_ANCHOR,
    PIPELINE_STEP,
    install_pipeline_step,
    resolve_target_username,
    sync_wikimedia_username,
)

SET_COOKIES = "common.djangoapps.third_party_auth.pipeline.set_logged_in_cookies"

BASE_PIPELINE = [
    "social_core.pipeline.social_auth.social_user",
    "common.djangoapps.third_party_auth.pipeline.ensure_user_information",
    "social_core.pipeline.user.user_details",
    PIPELINE_ANCHOR,
    SET_COOKIES,
]


def _backend(name="wikimediaIdentityServer"):
    # `name` is reserved by Mock's constructor, so it has to be set afterwards.
    backend = mock.Mock()
    backend.name = name
    return backend


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("MerryJupiter", "MerryJupiter"),
        ("  MerryJupiter  ", "MerryJupiter"),
        ("", ""),
        (None, ""),
    ],
)
def test_resolve_target_username_normalises(raw, expected):
    assert resolve_target_username(raw) == expected


@override_settings(USERNAME_MAX_LENGTH=10)
def test_resolve_target_username_truncates_like_the_auth_pipeline():
    """
    A Wikimedia name longer than the limit must normalise to what `get_username`
    would have stored, or the account looks out of sync on every single login.
    """
    assert resolve_target_username("AVeryLongWikimediaName") == "AVeryLongW"


@override_settings(SOCIAL_AUTH_PIPELINE=list(BASE_PIPELINE))
def test_install_pipeline_step_inserts_after_the_anchor():
    from django.conf import settings

    install_pipeline_step()

    pipeline = settings.SOCIAL_AUTH_PIPELINE
    assert pipeline.index(PIPELINE_STEP) == pipeline.index(PIPELINE_ANCHOR) + 1
    # Must land before the cookies are written, so the JWT carries the new name.
    assert pipeline.index(PIPELINE_STEP) < pipeline.index(SET_COOKIES)


@override_settings(SOCIAL_AUTH_PIPELINE=list(BASE_PIPELINE))
def test_install_pipeline_step_is_idempotent():
    """ready() can run more than once; the step must not stack up."""
    from django.conf import settings

    install_pipeline_step()
    install_pipeline_step()

    assert settings.SOCIAL_AUTH_PIPELINE.count(PIPELINE_STEP) == 1


@override_settings(SOCIAL_AUTH_PIPELINE=["social_core.pipeline.social_auth.social_user"])
def test_install_pipeline_step_appends_when_the_anchor_is_gone():
    """Upstream could rename or drop `user_details_force_sync`; still install."""
    from django.conf import settings

    install_pipeline_step()

    assert settings.SOCIAL_AUTH_PIPELINE[-1] == PIPELINE_STEP


def test_install_pipeline_step_noop_without_a_pipeline():
    """CMS, and LMS with third-party auth off, have no pipeline to extend."""
    from django.conf import settings

    install_pipeline_step()

    assert not hasattr(settings, "SOCIAL_AUTH_PIPELINE")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"backend": _backend(), "details": {"username": "MerryJupiter"}, "user": None},
        {"backend": None, "details": {"username": "MerryJupiter"}, "user": mock.Mock(username="DrSallyAnne")},
        {
            "backend": _backend("google-oauth2"),
            "details": {"username": "MerryJupiter"},
            "user": mock.Mock(username="DrSallyAnne"),
        },
        {"backend": _backend(), "details": {}, "user": mock.Mock(username="DrSallyAnne")},
        {"backend": _backend(), "details": {"username": "DrSallyAnne"}, "user": mock.Mock(username="DrSallyAnne")},
    ],
    ids=["no user", "no backend", "other provider", "no username reported", "username unchanged"],
)
def test_sync_wikimedia_username_skips(kwargs):
    with mock.patch("openedx_wikilearn_features.username_sync.rename_user") as rename:
        sync_wikimedia_username(**kwargs)

    rename.assert_not_called()


def test_sync_wikimedia_username_renames_on_change():
    user = mock.Mock(username="DrSallyAnne")

    with mock.patch("openedx_wikilearn_features.username_sync.rename_user") as rename:
        sync_wikimedia_username(backend=_backend(), details={"username": "MerryJupiter"}, user=user)

    rename.assert_called_once_with(user, "MerryJupiter")


@override_settings(USERNAME_MAX_LENGTH=10)
def test_sync_wikimedia_username_renames_to_the_truncated_form():
    user = mock.Mock(username="OldName")

    with mock.patch("openedx_wikilearn_features.username_sync.rename_user") as rename:
        sync_wikimedia_username(backend=_backend(), details={"username": "AVeryLongWikimediaName"}, user=user)

    rename.assert_called_once_with(user, "AVeryLongW")


def test_sync_wikimedia_username_never_breaks_the_login():
    """A cosmetic sync failing must not cost the learner their session."""
    user = mock.Mock(username="DrSallyAnne")

    with mock.patch(
        "openedx_wikilearn_features.username_sync.rename_user",
        side_effect=RuntimeError("forums exploded"),
    ):
        sync_wikimedia_username(backend=_backend(), details={"username": "MerryJupiter"}, user=user)
