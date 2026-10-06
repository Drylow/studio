"""Keep the historical upload permissions separate from visibility management."""

import os

MANAGED_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
LEGACY_SCOPES = UPLOAD_SCOPE + " " + READ_SCOPE


def direct_news(channel):
    return (
        os.getenv("YOUTUBE_PUBLICATION_FLOW", "").strip() == "legacy-news"
        and channel["publication_mode"] == "news"
    )


def requested_scope(channel):
    return LEGACY_SCOPES if direct_news(channel) else MANAGED_SCOPE


def supports(scopes, requested):
    granted = set(scopes.split())
    return (
        bool(granted & {MANAGED_SCOPE, "https://www.googleapis.com/auth/youtube"})
        or set(requested.split()) <= granted
    )
