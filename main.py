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

# OWNER USERNAME / ID
OWNER_USERNAMES = ["jyoex", "shivuu_vxcom"]  # aapka TG username without @
AUTHORIZED_OFFICIAL_GROUP = "@Comchater"

FORCE_CHANNELS = [
    {"name": "Channel 1", "tag": "@jyoex", "link": "https://t.me/jyoex"},
    {"name": "Channel 2", "tag": "@Comchater", "link": "https://t.me/Comchater"},
    {"name": "Channel 3", "tag": "@Foraremy", "link": "https://t.me/Foraremy"}
]

CHECK_INTERVAL_SECONDS = 15
DB_FILE = "dual_tracker_db.json"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ----------------- DATABASE -----------------
def load_db():
    default_data = {
        "unban_monitors": {},
        "ban_monitors": {},
        "admin_ids": [],
        "media": {
            "m": "https://media.giphy.com/media/3o7TKTDnUxE0g2fSE8/giphy.gif",
            "ub": "https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif",
            "b": "https://media.giphy.com/media/l2YWg3f6m0tI7Ff2w/giphy.gif",
            "deny": "https://media.giphy.com/media/13d2jHlSlxklVe/giphy.gif"
        }
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "media" not in data:
                    data["media"] = default_data["media"]
                if "admin_ids" not in data:
                    data["admin_ids"] = []
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

def is_owner(user):
    if not user:
        return False
    u_name = (user.username or "").lower().replace("@", "")
    if u_name in [x.lower() for x in OWNER_USERNAMES]:
        if user.id not in db["admin_ids"]:
            db["admin_ids"].append(user.id)
            save_db(db)
        return True
    return user.id in db.get("admin_ids", [])

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

# ----------------- FORCE JOIN VERIFICATION -----------------
def get_missing_channels(user_id):
    missing = []
    for ch in FORCE_CHANNELS:
        try:
            member = bot.get_chat_member(ch["tag"], user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                missing.append(ch)
        except Exception as e:
            # Agar bot admin nahi hai to verify fail na kare
            print(f"Channel check warning for {ch['tag']}: {e}")
    return missing

def check_access(message):
    user = message.from_user
    chat_type = message.chat.type

    # 1. Owner has unconditional bypass
    if is_owner(user):
        return True

    # 2. Check Force Join Channels First
    missing = get_missing_channels(user.id)
    if missing:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in missing:
            markup.add(types.InlineKeyboardButton(f"Join {ch['tag']}", url=ch["link"]))
        
        user_name = user.first_name or "User"
        alert_msg = (
            "<b>Access Required</b>\n\n"
            f"Hello {user_name}, you must join all our required official channels to use this bot:\n\n"
            "• @jyoex\n"
            "• @Comchater\n"
            "• @Foraremy\n\n"
            "Click below to join and try again."
        )
        bot.reply_to(message, alert_msg, reply_markup=markup)
        return False

    # 3. If in Private DM: Tell user to use official group
    if chat_type == "private":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Official Group", url="https://t.me/Comchater"))
        bot.reply_to(
            message,
            "<b>Notice</b>\n\n"
            "Bot commands are locked in direct messages.\n"
            f"You can only use this bot inside our official group: <b>{AUTHORIZED_OFFICIAL_GROUP}</b>",
            reply_markup=markup
        )
        return False

    return True

# ----------------- ANTI-UNAUTHORIZED GROUP PROTECTION -----------------
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            # Bot was added to a group
            adder = message.from_user
            if not is_owner(adder):
                try:
                    bot.send_message(
                        message.chat.id,
                        "<b>Unauthorized Group</b>\n\n"
                        "This bot cannot be added by regular members.\n"
                        f"Official Group: {AUTHORIZED_OFFICIAL_GROUP}\n"
                        "Leaving chat now..."
                    )
                    bot.leave_chat(message.chat.id)
                except Exception:
                    pass

# ----------------- INSTAGRAM ENGINE -----------------
def get_instagram_details(username):
    username = username.strip().lower().replace("@", "")
    ds_user_id = INSTAGRAM_SESSION_ID.split(":")[0] if ":" in INSTAGRAM_SESSION_ID else ""

    # Method 1: Authenticated Mobile Internal API
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

    # Method 2: Web Profile API Layer
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

# ----------------- MEDIA SENDER HELPER -----------------
def send_custom_media(chat_id, media_url, caption, reply_to=None):
    try:
        if media_url.endswith(".mp4"):
            return bot.send_video(chat_id=chat_id, video=media_url, caption=caption, reply_to_message_id=reply_to)
        elif media_url.endswith(".gif"):
            return bot.send_animation(chat_id=chat_id, animation=media_url, caption=caption, reply_to_message_id=reply_to)
        else:
            return bot.send_photo(chat_id=chat_id, photo=media_url, caption=caption, reply_to_message_id=reply_to)
    except Exception:
        return bot.send_message(chat_id=chat_id, text=caption, reply_to_message_id=reply_to)

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
                    user_name = info.get("user_name", "User")

                    caption = (
                        "<b>Instagram Account Recovered</b>\n\n"
                        f"<b>@{username}</b>\n"
                        f"Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
                        f"Time Taken: <code>{time_str}</code>\n"
                        f"Recovered at: <code>{get_current_time_str()}</code>\n\n"
                        f"Requested by: <b>{user_name}</b>"
                    )

                    media_url = db.get("media", {}).get("ub")
                    sent_msg = send_custom_media(info["chat_id"], media_url, caption)
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
                        user_name = info.get("user_name", "User")

                        caption = (
                            "<b>Instagram Account Banned</b>\n\n"
                            f"<b>@{username}</b>\n"
                            f"Previous Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
                            f"Time Taken: <code>{time_str}</code>\n"
                            f"Banned at: <code>{get_current_time_str()}</code>\n\n"
                            f"Requested by: <b>{user_name}</b>"
                        )

                        media_url = db.get("media", {}).get("b")
                        sent_msg = send_custom_media(info["chat_id"], media_url, caption)
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

# ----------------- COMMAND HANDLERS -----------------
@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_access(message):
        return

    user_name = message.from_user.first_name or "User"
    welcome_text = (
        f"<b>Welcome {user_name}</b>\n\n"
        "<b>Commands:</b>\n"
        "• <code>/ub username</code> — Monitor account recovery / unban\n"
        "• <code>/b username</code> — Monitor account for ban\n"
        "• <code>/status</code> — Monitored accounts list\n"
        "• <code>/help</code> — Instructions\n\n"
        f"Powered by: {DEVELOPER_TAG}"
    )
    bot.reply_to(message, welcome_text)

# ----------------- /admin COMMAND (OWNER ONLY) -----------------
@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if not is_owner(message.from_user):
        bot.reply_to(message, "<b>Access Denied:</b> Owner permission required.")
        return
    
    admin_text = (
        "<b>Owner Control Panel</b>\n\n"
        "<b>Current Media Links:</b>\n"
        f"• Monitoring (m): <code>{db['media']['m']}</code>\n"
        f"• Unban Alert (ub): <code>{db['media']['ub']}</code>\n"
        f"• Ban Alert (b): <code>{db['media']['b']}</code>\n"
        f"• Deny Alert (deny): <code>{db['media']['deny']}</code>\n\n"
        "<b>Commands to Change:</b>\n"
        "• <code>/setpic m &lt;link&gt;</code>\n"
        "• <code>/setpic ub &lt;link&gt;</code>\n"
        "• <code>/setpic b &lt;link&gt;</code>\n"
        "• <code>/setpic deny &lt;link&gt;</code>\n\n"
        f"<i>Developer: {DEVELOPER_TAG}</i>"
    )
    bot.reply_to(message, admin_text)

@bot.message_handler(commands=['setpic'])
def handle_setpic(message):
    if not is_owner(message.from_user):
        return
    
    parts = message.text.split()
    if len(parts) < 3 or parts[1] not in ["m", "ub", "b", "deny"]:
        bot.reply_to(message, "<b>Usage:</b> <code>/setpic ub https://link-to-gif-or-photo.gif</code>")
        return

    pic_type = parts[1]
    url = parts[2]
    db.setdefault("media", {})[pic_type] = url
    save_db(db)
    bot.reply_to(message, f"<b>Success:</b> Media for <code>/{pic_type}</code> has been updated.")

# ----------------- /ub COMMAND -----------------
@bot.message_handler(commands=['ub', 'unban', 'm'])
def handle_unban_request(message):
    if not check_access(message):
        return

    username = extract_username(message)
    user_name = message.from_user.first_name or "User"

    if not username:
        bot.reply_to(message, "<b>Usage:</b> <code>/ub username</code>\n<b>Example:</b> <code>/ub gt5available</code>")
        return

    if username in db.get("unban_monitors", {}):
        bot.reply_to(message, f"<b>@{username}</b> is already being monitored.")
        return

    status = get_instagram_details(username)
    if status["active"] is True:
        f_by = format_count(status["followers"])
        f_to = format_count(status["following"])
        caption = (
            f"<b>@{username}</b> is already active.\n\n"
            f"Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
            f"Requested by: <b>{user_name}</b>"
        )
        deny_media = db.get("media", {}).get("deny")
        send_custom_media(message.chat.id, deny_media, caption, reply_to=message.message_id)
        return

    req_time = get_current_time_str()
    req_date = get_current_date_str()

    db.setdefault("unban_monitors", {})[username] = {
        "chat_id": message.chat.id,
        "user_id": message.from_user.id,
        "user_name": user_name,
        "start_time": time.time(),
        "requested_time": req_time,
        "requested_date": req_date
    }
    save_db(db)

    caption = (
        "<b>Instagram Account Monitoring</b>\n\n"
        f"<b>@{username}</b> added successfully.\n"
        "You'll be notified as soon as the account is active.\n\n"
        f"Requested by: <b>{user_name}</b>"
    )

    media_url = db.get("media", {}).get("m")
    send_custom_media(message.chat.id, media_url, caption, reply_to=message.message_id)

# ----------------- /b COMMAND -----------------
@bot.message_handler(commands=['b', 'ban'])
def handle_ban_request(message):
    if not check_access(message):
        return

    username = extract_username(message)
    user_name = message.from_user.first_name or "User"

    if not username:
        bot.reply_to(message, "<b>Usage:</b> <code>/b username</code>\n<b>Example:</b> <code>/b gt5available</code>")
        return

    if username in db.get("ban_monitors", {}):
        bot.reply_to(message, f"<b>@{username}</b> is already being monitored.")
        return

    status = get_instagram_details(username)
    if status["active"] is False:
        caption = (
            f"<b>@{username}</b> is already banned or unavailable.\n\n"
            f"Requested by: <b>{user_name}</b>"
        )
        deny_media = db.get("media", {}).get("deny")
        send_custom_media(message.chat.id, deny_media, caption, reply_to=message.message_id)
        return

    f_by = format_count(status["followers"])
    f_to = format_count(status["following"])
    req_time = get_current_time_str()
    req_date = get_current_date_str()

    db.setdefault("ban_monitors", {})[username] = {
        "chat_id": message.chat.id,
        "user_id": message.from_user.id,
        "user_name": user_name,
        "followers": status["followers"],
        "following": status["following"],
        "start_time": time.time(),
        "requested_time": req_time,
        "requested_date": req_date
    }
    save_db(db)

    caption = (
        "<b>Instagram Account Monitoring</b>\n\n"
        f"<b>@{username}</b> added successfully.\n"
        f"Current Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
        "You'll be notified as soon as the account is banned.\n\n"
        f"Requested by: <b>{user_name}</b>"
    )

    media_url = db.get("media", {}).get("m")
    send_custom_media(message.chat.id, media_url, caption, reply_to=message.message_id)

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

    lines = ["<b>Active Monitors</b>\n"]
    if unbans:
        lines.append("<b>Awaiting Recovery:</b>")
        for u, d in unbans.items():
            t = format_time_taken(time.time() - d["start_time"])
            lines.append(f"• <b>@{u}</b> (Elapsed: <code>{t}</code>) — {d.get('user_name')}")

    if bans:
        lines.append("\n<b>Awaiting Ban:</b>")
        for u, d in bans.items():
            t = format_time_taken(time.time() - d["start_time"])
            f_by = format_count(d.get("followers", "N/A"))
            lines.append(f"• <b>@{u}</b> (Followers: <code>{f_by}</code> | Elapsed: <code>{t}</code>) — {d.get('user_name')}")

    bot.reply_to(message, "\n".join(lines))

# ----------------- /help COMMAND -----------------
@bot.message_handler(commands=['help', 'h'])
def handle_help(message):
    if not check_access(message):
        return
    help_text = (
        "<b>Help & Commands:</b>\n\n"
        "• <code>/ub username</code> — Monitor account recovery / unban\n"
        "• <code>/b username</code> — Monitor account for ban\n"
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
    print("Dual Tracker Bot with Strict Rules is active...")
    run_bot_polling()
