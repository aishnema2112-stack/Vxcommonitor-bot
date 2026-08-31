import os
import sys
import time
import json
import re
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from datetime import datetime, timezone, timedelta

# ----------------- TAMPER-PROOF CREDITS -----------------
DEVELOPER_TAG = "@jyoex"
DEV_CHANNEL = "JYOEX NETWORK"

def _verify_integrity():
    if DEVELOPER_TAG != "@jyoex" or DEV_CHANNEL != "JYOEX NETWORK":
        print("[SECURITY] Tamper detected.")
        sys.exit(1)

_verify_integrity()
# --------------------------------------------------------

# ----------------- 24/7 WEB SERVER FOR RENDER -----------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Dual Monitor Bot is Active 24/7")

    def log_message(self, format, *args):
        return

def run_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Web server error: {e}")

threading.Thread(target=run_server, daemon=True).start()
# -------------------------------------------------------------

# ----------------- CONFIGURATION -----------------
BOT_TOKEN = "8950259719:AAGW4Bf5vXmFBO6VaVSGedl1LgjHoLO5U-k"
INSTAGRAM_SESSION_ID = "70229745656:sLSyRu4K1KDgPw:11:AYg1H4LDg5LXUI5a3y8ebDWyAoexZ0jKncnz-WcYvA"

AUTHORIZED_OFFICIAL_GROUPS = ["comchater"]

FORCE_CHANNELS = [
    {"name": "📢 Jyoex", "tag": "@jyoex", "link": "https://t.me/jyoex"},
    {"name": "📢 Comchater", "tag": "@Comchater", "link": "https://t.me/Comchater"},
    {"name": "📢 Foraremy", "tag": "@Foraremy", "link": "https://t.me/Foraremy"}
]

CHECK_INTERVAL_SECONDS = 15
DB_FILE = "dual_tracker_db.json"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Temporary state for Admin Media upload
admin_upload_state = {}

# ----------------- DATABASE -----------------
def load_db():
    default_data = {
        "unban_monitors": {},
        "ban_monitors": {},
        "admins": [],
        "media": {
            "m": {"type": "animation", "id": "https://media.giphy.com/media/3o7TKTDnUxE0g2fSE8/giphy.gif"},
            "ub": {"type": "animation", "id": "https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif"},
            "b": {"type": "animation", "id": "https://media.giphy.com/media/l2YWg3f6m0tI7Ff2w/giphy.gif"},
            "deny": {"type": "animation", "id": "https://media.giphy.com/media/13d2jHlSlxklVe/giphy.gif"}
        }
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "media" not in data:
                    data["media"] = default_data["media"]
                if "admins" not in data:
                    data["admins"] = []
                return data
        except Exception:
            return default_data
    return default_data

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"DB Error: {e}")

db = load_db()

# ----------------- HELPERS -----------------
IST = timezone(timedelta(hours=5, minutes=30))

def get_current_time_str():
    return datetime.now(IST).strftime("%I:%M %p")

def get_current_date_str():
    return datetime.now(IST).strftime("%d %b, %Y")

def get_user_mention(user_id, first_name):
    clean_name = first_name.replace("<", "").replace(">", "") if first_name else "User"
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'

def is_admin_or_owner(user_id, username=None):
    if user_id in db.get("admins", []):
        return True
    if username and username.lower().replace("@", "") in ["jyoex", "shivuu_vxcom", "shivuu"]:
        if user_id not in db["admins"]:
            db["admins"].append(user_id)
            save_db(db)
        return True
    return False

def format_count(count):
    if isinstance(count, str):
        count_clean = count.replace(",", "").strip()
        if count_clean.isdigit():
            count = int(count_clean)
        else:
            return count
    if not isinstance(count, (int, float)):
        return "N/A"
    
    if count >= 1_000_000:
        val = count / 1_000_000
        return f"{val:.1f}M" if val % 1 != 0 else f"{int(val)}M"
    elif count >= 1_000:
        val = count / 1_000
        return f"{val:.1f}k" if val % 1 != 0 else f"{int(val)}k"
    return str(count)

def format_time_taken(seconds_elapsed):
    days = int(seconds_elapsed // 86400)
    hours = int((seconds_elapsed % 86400) // 3600)
    minutes = int((seconds_elapsed % 3600) // 60)
    seconds = int(seconds_elapsed % 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts) if parts else "0s"

def extract_username(message):
    if not message.text:
        return None
    parts = message.text.split()
    if len(parts) < 2:
        return None
    raw = parts[1].strip().lower().replace("@", "")
    clean = re.sub(r'[^a-z0-9._]', '', raw)
    return clean if clean else None

# ----------------- MEDIA SENDER ENGINE -----------------
def send_custom_media(chat_id, key, caption, reply_to=None):
    media_data = db.get("media", {}).get(key)
    if not media_data:
        return bot.send_message(chat_id=chat_id, text=caption, reply_to_message_id=reply_to)

    if isinstance(media_data, str):
        m_type = "animation" if media_data.endswith(".gif") else "photo"
        m_id = media_data
    else:
        m_type = media_data.get("type", "photo")
        m_id = media_data.get("id", "")

    try:
        if m_type == "video":
            return bot.send_video(chat_id=chat_id, video=m_id, caption=caption, reply_to_message_id=reply_to)
        elif m_type == "animation":
            return bot.send_animation(chat_id=chat_id, animation=m_id, caption=caption, reply_to_message_id=reply_to)
        elif m_type == "photo":
            return bot.send_photo(chat_id=chat_id, photo=m_id, caption=caption, reply_to_message_id=reply_to)
        else:
            return bot.send_photo(chat_id=chat_id, photo=m_id, caption=caption, reply_to_message_id=reply_to)
    except Exception as e:
        print(f"Media send failed, falling to text fallback: {e}")
        return bot.send_message(chat_id=chat_id, text=caption, reply_to_message_id=reply_to)

# ----------------- FORCE JOIN VERIFICATION -----------------
def get_missing_channels(user_id):
    missing = []
    for ch in FORCE_CHANNELS:
        try:
            member = bot.get_chat_member(ch["tag"], user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                missing.append(ch)
        except Exception:
            pass
    return missing

def build_force_join_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in FORCE_CHANNELS:
        markup.add(types.InlineKeyboardButton(ch["name"], url=ch["link"]))
    markup.add(types.InlineKeyboardButton("✅ Verify / Try Again", callback_data="verify_channels"))
    return markup

def check_access(message):
    user = message.from_user
    chat = message.chat

    if is_admin_or_owner(user.id, user.username):
        return True

    missing = get_missing_channels(user.id)
    if missing:
        mention = get_user_mention(user.id, user.first_name)
        text = (
            f"⚠️ <b>Access Restricted</b>\n\n"
            f"Hello {mention}, you must join all our official channels before using this bot:\n\n"
            "• @jyoex\n• @Comchater\n• @Foraremy\n\n"
            "<i>Click below to join and press Verify:</i>"
        )
        bot.reply_to(message, text, reply_markup=build_force_join_markup())
        return False

    if chat.type == "private":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Official Group", url="https://t.me/Comchater"))
        mention = get_user_mention(user.id, user.first_name)
        bot.reply_to(
            message,
            f"ℹ️ <b>Notice</b>\n\n"
            f"{mention}, bot commands are only allowed inside <b>@Comchater</b>.",
            reply_markup=markup
        )
        return False

    return True

@bot.callback_query_handler(func=lambda call: call.data == "verify_channels")
def handle_verify_callback(call):
    missing = get_missing_channels(call.from_user.id)
    if missing:
        bot.answer_callback_query(call.id, "❌ You haven't joined all channels yet! Please join and try again.", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "✅ Verified! You can now use the bot in @Comchater", show_alert=True)
        try:
            bot.edit_message_text(
                "✅ <b>Access Granted!</b> You can now use commands in our official group <b>@Comchater</b>.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
        except Exception:
            pass

# ----------------- ANTI-UNAUTHORIZED GROUP PROTECTION -----------------
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            chat_username = (message.chat.username or "").lower()
            
            if chat_username in AUTHORIZED_OFFICIAL_GROUPS:
                try:
                    bot.send_message(message.chat.id, "<b>Bot is active in @Comchater!</b>")
                except Exception:
                    pass
                return

            if is_admin_or_owner(message.from_user.id, message.from_user.username):
                return

            try:
                bot.send_message(
                    message.chat.id,
                    "<b>Unauthorized Group</b>\n\n"
                    "This bot only works inside @Comchater.\nLeaving now..."
                )
                bot.leave_chat(message.chat.id)
            except Exception:
                pass

# ----------------- INSTAGRAM ENGINE -----------------
def get_instagram_details(username):
    username = username.strip().lower().replace("@", "")
    ds_user_id = INSTAGRAM_SESSION_ID.split(":")[0] if ":" in INSTAGRAM_SESSION_ID else ""

    try:
        url = f"https://i.instagram.com/api/v1/users/{username}/usernameinfo/"
        headers = {
            "User-Agent": "Instagram 278.0.0.19.115 Android (33/13; 440dpi; 1080x2400; Xiaomi; sweet; en_US; 458229237)",
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}; ds_user_id={ds_user_id};",
            "X-IG-App-ID": "936619743392459"
        }
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            user = res.json().get("user", {})
            if user:
                return {
                    "active": True,
                    "followers": user.get("follower_count", 0),
                    "following": user.get("following_count", 0)
                }
        elif res.status_code == 404:
            return {"active": False, "followers": 0, "following": 0}
    except Exception:
        pass

    try:
        web_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        web_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "x-ig-app-id": "936619743392459",
            "Referer": f"https://www.instagram.com/{username}/",
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}; ds_user_id={ds_user_id};"
        }
        res2 = requests.get(web_url, headers=web_headers, timeout=6)
        if res2.status_code == 200:
            data = res2.json().get("data", {}).get("user")
            if data:
                return {
                    "active": True,
                    "followers": data.get("edge_followed_by", {}).get("count", 0),
                    "following": data.get("edge_follow", {}).get("count", 0)
                }
            return {"active": False, "followers": 0, "following": 0}
        elif res2.status_code == 404:
            return {"active": False, "followers": 0, "following": 0}
    except Exception:
        pass

    return {"active": False, "followers": 0, "following": 0}

# ----------------- BACKGROUND MONITOR LOOP -----------------
def monitor_loop():
    while True:
        try:
            _verify_integrity()

            # 1. Recovery Check (/ub)
            unban_list = list(db.get("unban_monitors", {}).items())
            for username, info in unban_list:
                status = get_instagram_details(username)
                if status["active"] is True:
                    elapsed = time.time() - info.get("start_time", time.time())
                    time_str = format_time_taken(elapsed)
                    f_by = format_count(status["followers"])
                    f_to = format_count(status["following"])
                    user_mention = get_user_mention(info.get("user_id"), info.get("user_name"))

                    caption = (
                        "🎉 <b>Instagram Account Recovered</b>\n\n"
                        f"Target: <b>@{username}</b>\n"
                        f"Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
                        f"Time Taken: <code>{time_str}</code>\n"
                        f"Recovered at: <code>{get_current_time_str()}</code>\n\n"
                        f"👤 Requested by: {user_mention}"
                    )

                    sent_msg = send_custom_media(info["chat_id"], "ub", caption)
                    try:
                        bot.pin_chat_message(info["chat_id"], sent_msg.message_id)
                    except Exception:
                        pass

                    del db["unban_monitors"][username]
                    save_db(db)

                time.sleep(2)

            # 2. Ban Check (/b)
            ban_list = list(db.get("ban_monitors", {}).items())
            for username, info in ban_list:
                status = get_instagram_details(username)
                if status["active"] is False:
                    time.sleep(3)
                    recheck = get_instagram_details(username)
                    if recheck["active"] is False:
                        elapsed = time.time() - info.get("start_time", time.time())
                        time_str = format_time_taken(elapsed)
                        f_by = format_count(info.get("followers", "N/A"))
                        f_to = format_count(info.get("following", "N/A"))
                        user_mention = get_user_mention(info.get("user_id"), info.get("user_name"))

                        caption = (
                            "🚫 <b>Instagram Account Banned</b>\n\n"
                            f"Target: <b>@{username}</b>\n"
                            f"Previous Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
                            f"Time Taken: <code>{time_str}</code>\n"
                            f"Banned at: <code>{get_current_time_str()}</code>\n\n"
                            f"👤 Requested by: {user_mention}"
                        )

                        sent_msg = send_custom_media(info["chat_id"], "b", caption)
                        try:
                            bot.pin_chat_message(info["chat_id"], sent_msg.message_id)
                        except Exception:
                            pass

                        del db["ban_monitors"][username]
                        save_db(db)

                time.sleep(2)

            time.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(10)

threading.Thread(target=monitor_loop, daemon=True).start()

# ----------------- ADMIN INTERACTIVE PANEL -----------------
@bot.message_handler(commands=['claim'])
def handle_claim(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if user_id not in db["admins"]:
        db["admins"].append(user_id)
        save_db(db)
    bot.reply_to(message, "👑 <b>Success:</b> You are now registered as Owner/Admin! Send <code>/admin</code> to open settings.")

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    user_id = message.from_user.id
    if not is_admin_or_owner(user_id, message.from_user.username):
        bot.reply_to(message, "<b>Access Denied:</b> Send <code>/claim</code> in private DM first.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 Change /m GIF", callback_data="set_m"),
        types.InlineKeyboardButton("⚡ Change /ub GIF", callback_data="set_ub"),
        types.InlineKeyboardButton("🚫 Change /b GIF", callback_data="set_b"),
        types.InlineKeyboardButton("⚠️ Change Deny GIF", callback_data="set_deny"),
        types.InlineKeyboardButton("👁️ View Media", callback_data="view_media"),
        types.InlineKeyboardButton("❌ Close", callback_data="close_admin")
    )

    admin_text = (
        "⚙️ <b>Bot Media Settings Panel</b>\n\n"
        "Click on any button below to change its GIF/Photo.\n"
        "After clicking, just directly send the Photo, GIF, or Video in chat!"
    )
    bot.reply_to(message, admin_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_"))
def handle_set_media_prompt(call):
    user_id = call.from_user.id
    if not is_admin_or_owner(user_id, call.from_user.username):
        return

    action = call.data.replace("set_", "")
    admin_upload_state[user_id] = action

    names = {"m": "Monitoring (/m)", "ub": "Unban Recovery (/ub)", "b": "Ban Alert (/b)", "deny": "Deny / Active Alert"}
    
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"📸 <b>Send Media for {names.get(action, action)}</b>\n\n"
        "Please send or forward the <b>Photo, GIF, or Video</b> right now in this chat."
    )

@bot.callback_query_handler(func=lambda call: call.data == "view_media")
def handle_view_media(call):
    bot.answer_callback_query(call.id)
    for key, name in [("m", "Monitoring"), ("ub", "Unban"), ("b", "Ban"), ("deny", "Deny")]:
        send_custom_media(call.message.chat.id, key, f"Current Media for <b>{name}</b>")
        time.sleep(0.5)

@bot.callback_query_handler(func=lambda call: call.data == "close_admin")
def handle_close_admin(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

# Listener for Admin Media Uploads
@bot.message_handler(content_types=['photo', 'animation', 'video', 'document'], func=lambda msg: msg.from_user.id in admin_upload_state)
def process_admin_media_upload(message):
    user_id = message.from_user.id
    action = admin_upload_state.get(user_id)
    if not action:
        return

    m_type = "photo"
    file_id = ""

    if message.animation:
        m_type = "animation"
        file_id = message.animation.file_id
    elif message.video:
        m_type = "video"
        file_id = message.video.file_id
    elif message.photo:
        m_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.document:
        m_type = "animation" if message.document.mime_type == "video/mp4" else "photo"
        file_id = message.document.file_id

    if file_id:
        db.setdefault("media", {})[action] = {"type": m_type, "id": file_id}
        save_db(db)
        del admin_upload_state[user_id]
        bot.reply_to(message, f"✅ <b>Success:</b> Media for <code>/{action}</code> updated successfully!")
    else:
        bot.reply_to(message, "❌ Failed to detect media. Please send a valid Photo, GIF, or Video.")

# ----------------- COMMAND HANDLERS -----------------
@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_access(message):
        return

    mention = get_user_mention(message.from_user.id, message.from_user.first_name)
    welcome_text = (
        f"👋 <b>Welcome {mention}</b>\n\n"
        "<b>Available Commands:</b>\n"
        "• <code>/ub username</code> — Monitor account recovery / unban\n"
        "• <code>/b username</code> — Monitor account for ban\n"
        "• <code>/status</code> — Monitored accounts list\n"
        "• <code>/help</code> — Instructions\n\n"
        f"Powered by: {DEVELOPER_TAG}"
    )
    bot.reply_to(message, welcome_text)

# ----------------- /ub COMMAND -----------------
@bot.message_handler(commands=['ub', 'unban', 'm'])
def handle_unban_request(message):
    if not check_access(message):
        return

    username = extract_username(message)
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "User"
    user_mention = get_user_mention(user_id, user_name)

    if not username:
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/ub username</code>\n<b>Example:</b> <code>/ub gt5available</code>")
        return

    if username in db.get("unban_monitors", {}):
        bot.reply_to(message, f"⚠️ <b>@{username}</b> is already being monitored.")
        return

    status = get_instagram_details(username)
    if status["active"] is True:
        f_by = format_count(status["followers"])
        f_to = format_count(status["following"])
        caption = (
            f"ℹ️ <b>@{username}</b> is already active.\n\n"
            f"Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
            f"👤 Requested by: {user_mention}"
        )
        send_custom_media(message.chat.id, "deny", caption, reply_to=message.message_id)
        return

    req_time = get_current_time_str()
    req_date = get_current_date_str()

    db.setdefault("unban_monitors", {})[username] = {
        "chat_id": message.chat.id,
        "user_id": user_id,
        "user_name": user_name,
        "start_time": time.time(),
        "requested_time": req_time,
        "requested_date": req_date
    }
    save_db(db)

    caption = (
        "🔍 <b>Instagram Account Monitoring Added</b>\n\n"
        f"Target: <b>@{username}</b>\n"
        "You'll be notified as soon as the account is active.\n\n"
        f"👤 Requested by: {user_mention}"
    )

    send_custom_media(message.chat.id, "m", caption, reply_to=message.message_id)

# ----------------- /b COMMAND -----------------
@bot.message_handler(commands=['b', 'ban'])
def handle_ban_request(message):
    if not check_access(message):
        return

    username = extract_username(message)
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "User"
    user_mention = get_user_mention(user_id, user_name)

    if not username:
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/b username</code>\n<b>Example:</b> <code>/b gt5available</code>")
        return

    if username in db.get("ban_monitors", {}):
        bot.reply_to(message, f"⚠️ <b>@{username}</b> is already being monitored.")
        return

    status = get_instagram_details(username)
    if status["active"] is False:
        caption = (
            f"ℹ️ <b>@{username}</b> is already banned or unavailable.\n\n"
            f"👤 Requested by: {user_mention}"
        )
        send_custom_media(message.chat.id, "deny", caption, reply_to=message.message_id)
        return

    f_by = format_count(status["followers"])
    f_to = format_count(status["following"])
    req_time = get_current_time_str()
    req_date = get_current_date_str()

    db.setdefault("ban_monitors", {})[username] = {
        "chat_id": message.chat.id,
        "user_id": user_id,
        "user_name": user_name,
        "followers": status["followers"],
        "following": status["following"],
        "start_time": time.time(),
        "requested_time": req_time,
        "requested_date": req_date
    }
    save_db(db)

    caption = (
        "🔍 <b>Instagram Account Monitoring Added</b>\n\n"
        f"Target: <b>@{username}</b>\n"
        f"Current Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
        "You'll be notified as soon as the account is banned.\n\n"
        f"👤 Requested by: {user_mention}"
    )

    send_custom_media(message.chat.id, "m", caption, reply_to=message.message_id)

# ----------------- /status COMMAND -----------------
@bot.message_handler(commands=['status', 's'])
def handle_status(message):
    if not check_access(message):
        return

    unbans = db.get("unban_monitors", {})
    bans = db.get("ban_monitors", {})

    if not unbans and not bans:
        bot.reply_to(message, "No active accounts in monitoring list.")
        return

    lines = ["📊 <b>Active Monitors</b>\n"]
    if unbans:
        lines.append("<b>Awaiting Recovery (/ub):</b>")
        for u, d in unbans.items():
            t = format_time_taken(time.time() - d["start_time"])
            mention = get_user_mention(d.get("user_id"), d.get("user_name"))
            lines.append(f"• <b>@{u}</b> (Elapsed: <code>{t}</code>) — {mention}")

    if bans:
        lines.append("\n<b>Awaiting Ban (/b):</b>")
        for u, d in bans.items():
            t = format_time_taken(time.time() - d["start_time"])
            f_by = format_count(d.get("followers", "N/A"))
            mention = get_user_mention(d.get("user_id"), d.get("user_name"))
            lines.append(f"• <b>@{u}</b> (Followers: <code>{f_by}</code> | Elapsed: <code>{t}</code>) — {mention}")

    bot.reply_to(message, "\n".join(lines))

# ----------------- /help COMMAND -----------------
@bot.message_handler(commands=['help', 'h'])
def handle_help(message):
    if not check_access(message):
        return
    help_text = (
        "📖 <b>Help & Commands:</b>\n\n"
        "• <code>/ub username</code> — Monitor recovery / unban\n"
        "• <code>/b username</code> — Monitor ban\n"
        "• <code>/status</code> — Check active monitors"
    )
    bot.reply_to(message, help_text)

# ----------------- POLLING -----------------
def run_bot_polling():
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=15, skip_pending=True)
        except Exception as e:
            print(f"[RECONNECT] {e}. Reconnecting in 3s...")
            time.sleep(3)

if __name__ == "__main__":
    _verify_integrity()
    print("Dual Tracker Bot is active...")
    run_bot_polling()
