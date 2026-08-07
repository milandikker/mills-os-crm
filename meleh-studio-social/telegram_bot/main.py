"""
Telegram Review Bot (step d).

Mobile-friendly companion to the Content Studio dashboard (step c) --
same content_queue rows, reachable from your phone without needing the
SSH tunnel the dashboard requires.

Same safety rule as the dashboard: never touches 'approved'. Buttons
here go straight from 'pending' to 'posted' or 'rejected', because the
Poster Agent polls for 'approved' rows and would stub-"publish" (fake)
and mark one 'posted' on its own -- using 'approved' here would let
that race ahead of you actually posting anything real.

Two background jobs, both polling content_queue:
  notify_new_drafts -- sends any not-yet-sent 'pending' row to you with
                        Posted/Reject buttons, and records the Telegram
                        message ID so it's never sent twice.
  send_reminders    -- past review_deadline (4h after creation) with no
                        response yet, sends ONE reminder ping. Never an
                        automatic status change -- just a nudge.
"""
import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from shared.db import dict_cursor, get_connection

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("telegram_bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
UPLOAD_DIR = os.environ.get("CONTENT_STUDIO_UPLOAD_DIR", "/app/uploads")
POLL_INTERVAL_SECONDS = int(os.environ.get("TELEGRAM_POLL_INTERVAL_SECONDS", 60))


def _media_path_or_url(media_url):
    """Local file path for dashboard-uploaded media (Telegram can't reach
    127.0.0.1:8000 to fetch it itself), or the URL as-is for a pasted
    external link (Telegram fetches those directly)."""
    if not media_url:
        return None
    if media_url.startswith("/media/"):
        return os.path.join(UPLOAD_DIR, media_url.removeprefix("/media/"))
    return media_url


def _is_video(media_url):
    return bool(media_url) and media_url.lower().endswith((".mp4", ".mov"))


def _keyboard(item_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ I posted this", callback_data=f"posted:{item_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject:{item_id}"),
    ]])


def _caption_text(item):
    text = f"#{item['id']} -- {item['platform']} / {item['content_type']}\n\n{item['caption']}"
    if item["media_note"]:
        text += f"\n\n[{item['media_note']}]"
    return text


async def notify_new_drafts(context: ContextTypes.DEFAULT_TYPE):
    with get_connection() as conn, dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM content_queue "
            "WHERE status = 'pending' AND telegram_message_id IS NULL "
            "ORDER BY created_at ASC"
        )
        rows = cur.fetchall()

        for item in rows:
            media = _media_path_or_url(item["media_url"])
            text = _caption_text(item)
            markup = _keyboard(item["id"])
            try:
                if media and _is_video(media):
                    msg = await context.bot.send_video(CHAT_ID, video=media, caption=text, reply_markup=markup)
                elif media:
                    msg = await context.bot.send_photo(CHAT_ID, photo=media, caption=text, reply_markup=markup)
                else:
                    msg = await context.bot.send_message(CHAT_ID, text=text, reply_markup=markup)
            except Exception:
                log.exception("Failed to send draft #%s to Telegram", item["id"])
                continue

            with conn.cursor() as write_cur:
                write_cur.execute(
                    "UPDATE content_queue SET telegram_message_id = %s WHERE id = %s",
                    (msg.message_id, item["id"]),
                )
            conn.commit()
            log.info("Sent draft #%s to Telegram", item["id"])


async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    with get_connection() as conn, dict_cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM content_queue "
            "WHERE status = 'pending' AND telegram_message_id IS NOT NULL "
            "AND telegram_reminded_at IS NULL AND review_deadline < now()"
        )
        rows = cur.fetchall()

        for item in rows:
            try:
                await context.bot.send_message(
                    CHAT_ID,
                    text=f"⏰ Still waiting on #{item['id']} -- posted it, or want to reject it?",
                    reply_to_message_id=item["telegram_message_id"],
                )
            except Exception:
                log.exception("Failed to send reminder for #%s", item["id"])
                continue

            with conn.cursor() as write_cur:
                write_cur.execute(
                    "UPDATE content_queue SET telegram_reminded_at = now() WHERE id = %s",
                    (item["id"],),
                )
            conn.commit()
            log.info("Sent reminder for #%s", item["id"])


async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if update.effective_chat.id != CHAT_ID:
        await query.answer("Not authorized.")
        return

    action, item_id_str = query.data.split(":")
    item_id = int(item_id_str)

    with get_connection() as conn, conn.cursor() as cur:
        if action == "posted":
            cur.execute(
                "UPDATE content_queue SET status = 'posted', posted_at = now() "
                "WHERE id = %s AND status = 'pending' RETURNING id",
                (item_id,),
            )
        elif action == "reject":
            cur.execute(
                "UPDATE content_queue SET status = 'rejected' "
                "WHERE id = %s AND status = 'pending' RETURNING id",
                (item_id,),
            )
        else:
            await query.answer("Unknown action.")
            return

        updated = cur.fetchone()
        conn.commit()

    if not updated:
        await query.answer("Already handled.")
        return

    label = "✅ Posted" if action == "posted" else "❌ Rejected"
    await query.answer(label)

    try:
        if query.message.caption is not None:
            await query.edit_message_caption(caption=f"{query.message.caption}\n\n{label}", reply_markup=None)
        else:
            await query.edit_message_text(text=f"{query.message.text}\n\n{label}", reply_markup=None)
    except Exception:
        log.exception("Failed to update message after action on #%s", item_id)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_action))
    app.job_queue.run_repeating(notify_new_drafts, interval=POLL_INTERVAL_SECONDS, first=5)
    app.job_queue.run_repeating(send_reminders, interval=POLL_INTERVAL_SECONDS, first=10)
    log.info("Telegram Review Bot starting, poll interval=%ss", POLL_INTERVAL_SECONDS)
    app.run_polling()


if __name__ == "__main__":
    main()
