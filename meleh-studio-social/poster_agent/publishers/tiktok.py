"""
Stub publisher for TikTok video posts.

TODO(step e): replace this stub with real TikTok publishing.
Two paths to evaluate when we get here:
  1. TikTok Content Posting API directly (needs its own app review/audit).
  2. Higgsfield's native TikTok tools (tiktok_connect / tiktok_publish /
     tiktok_publish_status) -- likely the simpler path since Higgsfield is
     already generating the video, and its TikTok connect flow skips us
     having to build + maintain our own TikTok API integration.
Decide between these once we're actually ready to wire this up.

Needs from .env: TIKTOK_ACCESS_TOKEN (only relevant for path 1).
"""


def publish(row):
    """Pretend to publish a TikTok video.

    `row` is a dict-like content_queue row (see shared/db.py dict_cursor).
    Returns a small result dict -- real version will return TikTok's
    published post ID here instead of None.
    """
    media_description = row["media_url"] or row["media_note"]
    print(
        f"[tiktok stub] Would publish {row['content_type']} to TikTok | "
        f"media={media_description!r} | caption={row['caption'][:60]!r}..."
    )
    return {"stub": True, "platform_post_id": None}
