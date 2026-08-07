"""
Stub publisher for TikTok video posts.

TODO(step e): replace this stub with real TikTok publishing.
Two paths to evaluate when we get here:
  1. TikTok Content Posting API directly -- confirmed as of 2026-08-07:
     unaudited apps can only post PRIVATELY (visible to no one but us),
     so this path is unusable for real marketing posts until TikTok's
     audit clears. That audit timeline is the real bottleneck here.
  2. Higgsfield's native TikTok tools (tiktok_connect / tiktok_publish /
     tiktok_publish_status) -- try this FIRST. If Higgsfield's own app is
     already TikTok-audited, publishing through their connected-account
     flow could let us skip TikTok's audit process entirely, not just
     skip building our own API integration. Worth confirming with
     Higgsfield directly before starting our own TikTok audit.
Decide between these once we're actually ready to wire this up.

Needs from .env: TIKTOK_ACCESS_TOKEN (only relevant for path 1).
"""


def publish(row):
    """Pretend to publish a TikTok video.

    `row` is a dict-like content_queue row (see shared/db.py dict_cursor).
    Returns a small result dict -- real version will return TikTok's
    published post ID here instead of None.
    """
    media_description = row["media_urls"] or row["media_note"]
    print(
        f"[tiktok stub] Would publish {row['content_type']} to TikTok | "
        f"media={media_description!r} | caption={row['caption'][:60]!r}..."
    )
    return {"stub": True, "platform_post_id": None}
