"""
Content Agent -- manual content dashboard (step c, v1).

Meta and TikTok API approval is pending, so the Poster Agent can't
actually publish anywhere yet -- it's still a stub. Until that's live,
posting happens by hand: you write/draft the post here, then publish it
yourself in the Instagram/TikTok app, then come back and mark it posted.

Deliberately stays off the 'approved' status. The Poster Agent polls for
'approved' rows and will (stub-)"publish" and mark them 'posted' on its
own within the hour -- if this dashboard used 'approved' for "ready to
post", the row would flip to 'posted' before you'd actually posted it
anywhere real. So this dashboard only ever writes 'pending', 'posted', or
'rejected' -- 'approved' stays reserved for when the full automated
pipeline (Content Agent draft -> Telegram review -> real Poster Agent
publish) is wired up later.
"""
import hmac
import os
import time
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from shared.db import dict_cursor, get_connection

load_dotenv()

UPLOAD_DIR = os.environ.get("CONTENT_STUDIO_UPLOAD_DIR", "/app/uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "mov"}

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ["CONTENT_STUDIO_SECRET_KEY"]

PLATFORM_CONTENT_TYPES = {
    "instagram": ["reel", "static"],
    "tiktok": ["tiktok_video"],
}


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

    with get_connection() as conn, dict_cursor(conn) as cur:
        if status == "all":
            cur.execute("SELECT * FROM content_queue ORDER BY created_at DESC")
        else:
            cur.execute(
                "SELECT * FROM content_queue WHERE status = %s ORDER BY created_at DESC",
                (status,),
            )
        items = cur.fetchall()

    return render_template("index.html", items=items, active_status=status)


@app.route("/new", methods=["GET", "POST"])
@require_auth
def new_item():
    if request.method == "GET":
        return render_template("new.html", platform_content_types=PLATFORM_CONTENT_TYPES)

    platform = request.form.get("platform", "")
    content_type = request.form.get("content_type", "")
    caption = request.form.get("caption", "").strip()
    media_note = request.form.get("media_note", "").strip() or None
    pasted_url = request.form.get("media_url", "").strip()

    if platform not in PLATFORM_CONTENT_TYPES:
        flash("Choose a valid platform.")
        return redirect(url_for("new_item"))
    if content_type not in PLATFORM_CONTENT_TYPES[platform]:
        flash("Choose a valid content type for that platform.")
        return redirect(url_for("new_item"))
    if not caption:
        flash("Caption is required.")
        return redirect(url_for("new_item"))

    media_url = pasted_url or None
    upload = request.files.get("media_file")
    if upload and upload.filename:
        if not allowed_file(upload.filename):
            flash("Unsupported file type. Use an image (png/jpg/gif/webp) or video (mp4/mov).")
            return redirect(url_for("new_item"))
        safe_name = secure_filename(upload.filename)
        stored_name = f"{int(time.time())}_{safe_name}"
        upload.save(os.path.join(UPLOAD_DIR, stored_name))
        media_url = f"/media/{stored_name}"

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO content_queue
                (platform, content_type, media_url, media_note, caption, status, review_deadline)
            VALUES (%s, %s, %s, %s, %s, 'pending', now() + interval '4 hours')
            """,
            (platform, content_type, media_url, media_note, caption),
        )
        conn.commit()

    flash("Draft created.")
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
        cur.execute(
            "UPDATE content_queue SET status = 'rejected' "
            "WHERE id = %s AND status = 'pending'",
            (item_id,),
        )
        conn.commit()
    flash(f"Rejected #{item_id}.")
    return redirect(request.referrer or url_for("index"))


@app.route("/media/<path:filename>")
@require_auth
def media(filename):
    safe_name = secure_filename(filename)
    if safe_name != filename:
        abort(404)
    return send_from_directory(UPLOAD_DIR, safe_name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
