"""
Real publisher for Instagram and Facebook via the Meta Graph API.

Needs from .env: META_GRAPH_API_TOKEN (long-lived Page access token),
META_PAGE_ID, META_IG_BUSINESS_ID.

Instagram (Content Publishing API). Every path polls status_code until
FINISHED before publishing, not just video -- confirmed by a real photo
post failing with "Media ID is not available" when published
immediately after container creation; Meta's own guidance is to always
confirm readiness first, images included:
  static (1 photo)   -> POST {ig-id}/media (image_url) -> wait -> media_publish
  static (2+ photos) -> POST {ig-id}/media per photo (is_carousel_item)
                         -> POST {ig-id}/media (media_type=CAROUSEL,
                            children=<ids>) -> wait -> media_publish
  reel (video)        -> POST {ig-id}/media (media_type=REELS, video_url)
                         -> wait (longer, real video processing) -> media_publish
Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing

Facebook (Page):
  static (1 photo)   -> POST {page-id}/photos (url, caption)
  static (2+ photos) -> POST {page-id}/photos per photo (published=false)
                         -> POST {page-id}/feed (attached_media=<ids>)
  reel (video)        -> POST {page-id}/videos (file_url, description)
                         -- this is a regular Page video upload, not the
                         dedicated Reels-placement API (which needs a
                         separate resumable-upload flow). Revisit if
                         Reels-specific placement/discovery matters.
  text-only            -> POST {page-id}/feed (message)
Docs: https://developers.facebook.com/docs/pages-api/posts

Real publishing needs the media URLs to be reachable by Meta's servers
-- that's why content_agent's /media/<filename> route no longer requires
login (see content_agent/app.py): Graph API has no way to pass our HTTP
basic auth credentials when it fetches image_url/video_url itself.

Needs CONTENT_STUDIO_PUBLIC_URL too: content_queue.media_urls stores
dashboard uploads as a relative path ("/media/xxx.png"), which only
means something inside our own Flask app. Meta's servers need a
complete, publicly fetchable URL, so every relative path gets that
public base URL prefixed before it's sent -- see _absolute_media_url.
"""
import json
import os
import time

import requests

GRAPH_API_BASE = "https://graph.facebook.com/v20.0"
VIDEO_POLL_INTERVAL_SECONDS = 3
VIDEO_POLL_TIMEOUT_SECONDS = 120


def _absolute_media_url(url):
    if url.startswith("/media/"):
        base = os.environ["CONTENT_STUDIO_PUBLIC_URL"].rstrip("/")
        return f"{base}{url}"
    return url


def _graph_request(method, path, **params):
    params["access_token"] = os.environ["META_GRAPH_API_TOKEN"]
    url = f"{GRAPH_API_BASE}/{path}"
    if method == "GET":
        resp = requests.get(url, params=params, timeout=30)
    else:
        resp = requests.post(url, data=params, timeout=30)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Meta Graph API error on {method} {path}: {data['error'].get('message')}")
    return data


def _wait_for_ig_media_ready(creation_id):
    """IG video containers process asynchronously -- poll until FINISHED
    before publishing, or raise on ERROR/EXPIRED/timeout."""
    elapsed = 0
    while elapsed < VIDEO_POLL_TIMEOUT_SECONDS:
        data = _graph_request("GET", creation_id, fields="status_code")
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram media processing failed: status_code={status}")
        time.sleep(VIDEO_POLL_INTERVAL_SECONDS)
        elapsed += VIDEO_POLL_INTERVAL_SECONDS
    raise RuntimeError("Instagram media processing timed out")


def _ig_publish(row):
    ig_id = os.environ["META_IG_BUSINESS_ID"]
    media_urls = [_absolute_media_url(u) for u in (row["media_urls"] or [])]
    caption = row["caption"]

    if row["content_type"] == "reel":
        if not media_urls:
            raise ValueError("Reel requires a video URL")
        container = _graph_request(
            "POST", f"{ig_id}/media",
            media_type="REELS", video_url=media_urls[0], caption=caption,
        )
        creation_id = container["id"]
    elif len(media_urls) > 1:
        child_ids = []
        for url in media_urls:
            child = _graph_request(
                "POST", f"{ig_id}/media",
                image_url=url, is_carousel_item="true",
            )
            child_ids.append(child["id"])
        container = _graph_request(
            "POST", f"{ig_id}/media",
            media_type="CAROUSEL", children=",".join(child_ids), caption=caption,
        )
        creation_id = container["id"]
    else:
        if not media_urls:
            raise ValueError("Static post requires at least one photo URL")
        container = _graph_request(
            "POST", f"{ig_id}/media",
            image_url=media_urls[0], caption=caption,
        )
        creation_id = container["id"]

    # Even photo containers can need a moment to finish processing before
    # they're publishable, not just video -- Meta's own recommended
    # practice is to always confirm status_code=FINISHED first.
    _wait_for_ig_media_ready(creation_id)
    published = _graph_request("POST", f"{ig_id}/media_publish", creation_id=creation_id)
    return published["id"]


def _fb_publish(row):
    page_id = os.environ["META_PAGE_ID"]
    media_urls = [_absolute_media_url(u) for u in (row["media_urls"] or [])]
    caption = row["caption"]

    if row["content_type"] == "reel":
        if not media_urls:
            raise ValueError("Video post requires a video URL")
        published = _graph_request(
            "POST", f"{page_id}/videos",
            file_url=media_urls[0], description=caption,
        )
        return published["id"]

    if len(media_urls) > 1:
        media_fbids = []
        for url in media_urls:
            uploaded = _graph_request(
                "POST", f"{page_id}/photos",
                url=url, published="false",
            )
            media_fbids.append(uploaded["id"])
        params = {"message": caption}
        for i, media_fbid in enumerate(media_fbids):
            params[f"attached_media[{i}]"] = json.dumps({"media_fbid": media_fbid})
        published = _graph_request("POST", f"{page_id}/feed", **params)
        return published["id"]

    if not media_urls:
        published = _graph_request("POST", f"{page_id}/feed", message=caption)
        return published["id"]

    published = _graph_request(
        "POST", f"{page_id}/photos",
        url=media_urls[0], caption=caption,
    )
    return published.get("post_id", published["id"])


def publish(row):
    """Publish an Instagram or Facebook post for real. `row` is a
    dict-like content_queue row (see shared/db.py dict_cursor). Returns
    the platform's real post ID. Raises on any Graph API error so the
    Poster Agent's existing retry/fail handling takes over."""
    if row["platform"] == "instagram":
        return _ig_publish(row)
    if row["platform"] == "facebook":
        return _fb_publish(row)
    raise ValueError(f"meta.py does not handle platform: {row['platform']}")
