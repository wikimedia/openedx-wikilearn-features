"""
Tests for the `wikimedia_general.mentions` module.
"""

import pytest

from openedx_wikilearn_features.wikimedia_general.mentions import extract_mentioned_usernames


def mention(username_attr, text=None):
    return (
        f'<span class="wikilearn-mention" data-username="{username_attr}" contenteditable="false">'
        f"@{text or username_attr}</span>&nbsp;"
    )


@pytest.mark.parametrize(
    "html, expected",
    [
        (f"<p>Hi {mention('Alice')}thanks</p>", ["Alice"]),
        (f"<p>{mention('Jane Doe')}and {mention('O&#39;Brien (WMF)')}</p>", ["Jane Doe", "O'Brien (WMF)"]),
        (f"<p>{mention('Tom &amp; &quot;Jerry&quot;')}</p>", ['Tom & "Jerry"']),
        (f"<p>{mention('Alice')}</p>", ["Alice"]),
        (f"<p>{mention('Alice')}{mention('Bob')}{mention('Alice')}</p>", ["Alice", "Bob"]),
        ('<span class="foo wikilearn-mention" data-username="Alice">@Alice</span>', ["Alice"]),
        # Plain-text @mentions are not notified
        ("<p>hello @Alice thanks</p>", []),
        ("@Jane Doe", []),
        ('<span class="other" data-username="Alice">@Alice</span>', []),
        ('<span class="wikilearn-mention">@Alice</span>', []),
        ('<span class="wikilearn-mention" data-username="">@</span>', []),
        ('<div class="wikilearn-mention" data-username="Alice">@Alice</div>', []),
        ("", []),
        (None, []),
    ],
)
def test_extract_mentioned_usernames(html, expected):
    assert extract_mentioned_usernames(html) == expected
