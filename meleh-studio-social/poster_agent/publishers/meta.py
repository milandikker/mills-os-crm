"""
Stub publisher for Instagram (and Facebook) via the Meta Graph API.

TODO(step e): replace this stub with real Meta Graph API calls.
We only ever post to our own owned Page / IG Business account. Try
adding that account as Admin/Developer/Tester on the Meta app first --
that path publishes without a formal App Review, and is very likely
sufficient since we're not publishing on behalf of any third party.
Fall back to App Review only if that role-based path proves
insufficient (unverified either way -- confirm empirically).

Real implementation will roughly be, for both static posts and Reels:
  1. POST /{ig-user-id}/media          -- create a media container
       (image_url=... for static, or media_type=REELS & video_url=...)
  2. POST /{ig-user-id}/media_publish  -- publish that container
     using the creation_id from step 1

Needs from .env: META_GRAPH_API_TOKEN (long-lived Page access token),
META_IG_BUSINESS_ID (and META_PAGE_ID if we also cross-post to Facebook).

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
"""


def publish(row):
    """Pretend to publish an Instagram or Facebook static post or Reel.

    `row` is a dict-like content_queue row (see shared/db.py dict_cursor).
    Returns a small result dict -- real version will return the Graph
    API's published media ID here instead of None.
    """
    media_description = row["media_urls"] or row["media_note"]
    print(
        f"[meta stub] Would publish {row['content_type']} to {row['platform'].capitalize()} | "
        f"media={media_description!r} | caption={row['caption'][:60]!r}..."
    )
    return {"stub": True, "platform_post_id": None}
