"""
Content Agent -- manual content dashboard (step c, v1).

Scheduled batch-publishing workflow: you create a week's worth of
already-decided content at once (each with its own scheduled_for time),
and the Telegram bot notifies you when each one's scheduled time
arrives instead of the moment you create it. Meta/TikTok API approval
is still pending, so posting still happens by hand at that point: you
publish it yourself in the Instagram/TikTok app, then come back and
mark it posted.

Step (e) real Meta publishing is live, so Instagram/Facebook drafts now
save straight to 'approved': the Poster Agent picks them up at
scheduled_for and posts for real, no manual click needed. TikTok still
only has a stub publisher (see poster_agent/publishers/tiktok.py), so
TikTok drafts still save as 'pending' and need the old manual
publish-yourself-then-click-"I posted this" flow -- flipping TikTok to
'approved' too would make the stub falsely mark it "posted" without any
real post happening.
"""
import hmac
import os
import time
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from shared.db import dict_cursor, get_connection

load_dotenv()

UPLOAD_DIR = os.environ.get("CONTENT_STUDIO_UPLOAD_DIR", "/app/uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "mov"}
MAX_CAROUSEL_IMAGES = 10

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ["CONTENT_STUDIO_SECRET_KEY"]

PLATFORMS = ["instagram", "facebook", "tiktok"]

# The dashboard asks for one simplified "kind" (what you're posting) per
# draft, since the same media/caption/schedule is usually going out to
# more than one platform at once -- this maps that kind to each
# platform's actual content_type value. 'video' -- exactly one video
# file. 'photo' -- one or more photos: a single photo, or a carousel
# when >1 (all three platforms support photo carousels, not just
# Instagram).
KIND_CONTENT_TYPES = {
    "video": {"instagram": "reel", "facebook": "reel", "tiktok": "tiktok_video"},
    "photo": {"instagram": "static", "facebook": "static", "tiktok": "static"},
}

# Platforms with a real publisher (poster_agent/publishers/meta.py) --
# their drafts save straight to 'approved' for automatic scheduled
# publishing. Platforms not listed here still save as 'pending' for the
# manual publish-yourself-then-mark-posted flow.
AUTO_PUBLISH_PLATFORMS = {"instagram", "facebook"}


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        expected_user = os.environ["CONTENT_STUDIO_USERNAME"]
        expected_pass = os.environ["CONTENT_STUDIO_PASSWORD"]
        valid = (
            auth is not None
            and hmac.compare_digest(auth.username or "", expected_user)
            and hmac.compare_digest(auth.password or "", expected_pass)
        )
        if not valid:
            return (
                "Login required",
                401,
                {"WWW-Authenticate": 'Basic realm="Content Studio"'},
            )
        return view(*args, **kwargs)

    return wrapped


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
@require_auth
def index():
    status = request.args.get("status", "pending")
    if status not in ("pending", "posted", "rejected", "all"):
        status = "pending"

    # Scheduled items are most useful soonest-first; everything else (a
    # history view) is most useful newest-first.
    order_by = "scheduled_for ASC" if status == "pending" else "created_at DESC"

    with get_connection() as conn, dict_cursor(conn) as cur:
        if status == "all":
            cur.execute(f"SELECT * FROM content_queue ORDER BY {order_by}")
        elif status == "pending":
            # The "Scheduled" tab covers both not-yet-resolved kinds of
            # draft: 'pending' (manual TikTok flow) and 'approved'
            # (auto-publish Instagram/Facebook flow, waiting for its
            # scheduled_for time).
            cur.execute(
                f"SELECT * FROM content_queue WHERE status IN ('pending', 'approved') ORDER BY {order_by}"
            )
        else:
            cur.execute(
                f"SELECT * FROM content_queue WHERE status = %s ORDER BY {order_by}",
                (status,),
            )
        items = cur.fetchall()

    return render_template("index.html", items=items, active_status=status)


@app.route("/new", methods=["GET", "POST"])
@require_auth
def new_item():
    if request.method == "GET":
        return render_template("new.html", platforms=PLATFORMS)

    platforms = [p for p in request.form.getlist("platforms") if p in PLATFORMS]
    kind = request.form.get("kind", "")
    caption = request.form.get("caption", "").strip()
    media_note = request.form.get("media_note", "").strip() or None
    pasted_url = request.form.get("media_url", "").strip()
    scheduled_for_raw = request.form.get("scheduled_for", "").strip()

    if not platforms:
        flash("Choose at least one platform.")
        return redirect(url_for("new_item"))
    if kind not in KIND_CONTENT_TYPES:
        flash("Choose whether this is a video or photo post.")
        return redirect(url_for("new_item"))
    if not caption:
        flash("Caption is required.")
        return redirect(url_for("new_item"))
    if not scheduled_for_raw:
        flash("Choose a scheduled date/time.")
        return redirect(url_for("new_item"))
    try:
        # JS on the form converts the browser's local datetime-local value
        # to a UTC ISO string before submit, so this is unambiguous
        # regardless of what timezone you're actually in when posting.
        scheduled_for = datetime.fromisoformat(scheduled_for_raw.replace("Z", "+00:00"))
    except ValueError:
        flash("Invalid scheduled date/time.")
        return redirect(url_for("new_item"))

    uploads = [f for f in request.files.getlist("media_file") if f and f.filename]

    if kind == "video" and len(uploads) > 1:
        flash("Video posts take a single video file, not multiple.")
        return redirect(url_for("new_item"))
    if kind == "photo" and len(uploads) > MAX_CAROUSEL_IMAGES:
        flash(f"Max {MAX_CAROUSEL_IMAGES} photos per carousel.")
        return redirect(url_for("new_item"))

    media_urls = []
    for i, upload in enumerate(uploads):
        if not allowed_file(upload.filename):
            flash("Unsupported file type. Use an image (png/jpg/gif/webp) or video (mp4/mov).")
            return redirect(url_for("new_item"))
        safe_name = secure_filename(upload.filename)
        stored_name = f"{int(time.time())}_{i}_{safe_name}"
        upload.save(os.path.join(UPLOAD_DIR, stored_name))
        media_urls.append(f"/media/{stored_name}")

    if pasted_url:
        media_urls.append(pasted_url)

    # One row per selected platform, all sharing the same media/caption/
    # schedule -- each platform still gets its own content_type value and
    # its own independent status, so e.g. an Instagram row can auto-publish
    # while its TikTok sibling still waits on a manual post.
    with get_connection() as conn, conn.cursor() as cur:
        for platform in platforms:
            content_type = KIND_CONTENT_TYPES[kind][platform]
            status = "approved" if platform in AUTO_PUBLISH_PLATFORMS else "pending"
            cur.execute(
                """
                INSERT INTO content_queue
                    (platform, content_type, media_urls, media_note, caption, status, scheduled_for, review_deadline)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (platform, content_type, media_urls, media_note, caption, status, scheduled_for, scheduled_for + timedelta(hours=4)),
            )
        conn.commit()

    flash(f"Scheduled to {', '.join(p.capitalize() for p in platforms)}.")
    return redirect(url_for("index"))


@app.route("/items/<int:item_id>/posted", methods=["POST"])
@require_auth
def mark_posted(item_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE content_queue SET status = 'posted', posted_at = now() "
            "WHERE id = %s AND status = 'pending'",
            (item_id,),
        )
        conn.commit()
    flash(f"Marked #{item_id} posted.")
    return redirect(request.referrer or url_for("index"))


@app.route("/items/<int:item_id>/reject", methods=["POST"])
@require_auth
def mark_rejected(item_id):
    with get_connection() as conn, conn.cursor() as cur:
        # Includes 'approved' so an auto-publish Instagram/Facebook draft
        # can still be cancelled before its scheduled_for time triggers
        # the Poster Agent to publish it for real.
        cur.execute(
            "UPDATE content_queue SET status = 'rejected' "
            "WHERE id = %s AND status IN ('pending', 'approved')",
            (item_id,),
        )
        conn.commit()
    flash(f"Rejected #{item_id}.")
    return redirect(request.referrer or url_for("index"))


@app.route("/media/<path:filename>")
def media(filename):
    # Deliberately no @require_auth: step (e)'s real Meta Graph API calls
    # fetch image_url/video_url directly from Meta's own servers, which
    # have no way to receive our HTTP basic auth credentials. Since this
    # content is either about to become a public post or already is one,
    # gating it here protected only the brief pre-publish window -- worth
    # trading for real publishing actually working. Filenames still carry
    # a timestamp + per-request index, so they aren't guessable/listable.
    safe_name = secure_filename(filename)
    if safe_name != filename:
        abort(404)
    return send_from_directory(UPLOAD_DIR, safe_name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
