"""
Helpers for finding @mentions inserted by the mention plugin in discussion posts.
"""
from html.parser import HTMLParser

MENTION_CLASS = "wikilearn-mention"


class _MentionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.usernames = []

    def handle_starttag(self, tag, attrs):
        if tag != "span":
            return
        attrs = dict(attrs)
        if MENTION_CLASS not in (attrs.get("class") or "").split():
            return
        username = attrs.get("data-username")
        if username and username not in self.usernames:
            self.usernames.append(username)


def extract_mentioned_usernames(html):
    """
    Return the unique usernames of the mention spans in ``html``, in order of appearance.
    """
    parser = _MentionParser()
    parser.feed(html or "")
    parser.close()
    return parser.usernames
