import os
import sys
import time
import json
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from datetime import datetime, timezone, timedelta

# ----------------- TAMPER-PROOF CREDIT INTEGRITY LOCK -----------------
DEVELOPER_TAG = "@jyoex"
DEV_CHANNEL = "JYOEX NETWORK"

def _verify_integrity():
    if DEVELOPER_TAG != "@jyoex" or DEV_CHANNEL != "JYOEX NETWORK":
        print("[CRITICAL SECURITY] Unauthorized tamper detected. Credits altered.")
        sys.exit(1)

_verify_integrity()
# ----------------------------------------------------------------------

# ----------------- 24/7 WEB SERVER FOR RENDER / UPTIMEROBOT -----------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Dual Tracker Bot by @jyoex is Online 24/7")

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
# ---------------------------------------------------------------------------

# ----------------- CONFIGURATION -----------------
BOT_TOKEN = "8950259719:AAGW4Bf5vXmFBO6VaVSGedl1LgjHoLO5U-k"
INSTAGRAM_SESSION_ID = "70229745656:sLSyRu4K1KDgPw:11:AYg1H4LDg5LXUI5a3y8ebDWyAoexZ0jKncnz-WcYvA"
CHECK_INTERVAL_SECONDS = 20
DB_FILE = "dual_tracker_db.json"

# Visual Media: Direct Anime MP4 Videos / Clips
MONITORING_VIDEO = "https://assets.mixkit.co/videos/preview/mixkit-digital-animation-of-screens-996-large.mp4"
UNBANNED_VIDEO = "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-background-1610-large.mp4"
BANNED_VIDEO = "https://assets.mixkit.co/videos/preview/mixkit-glitch-screen-effect-28795-large.mp4"
# --------------------------------------------------

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

try:
    bot.set_my_commands([
        types.BotCommand("ub", "Monitor account for recovery / unban"),
        types.BotCommand("b", "Monitor account for ban"),
        types.BotCommand("status", "Show active monitored accounts"),
        types.BotCommand("owner", "Bot Developer & Credits"),
        types.BotCommand("help", "Help & guide")
    ])
except Exception:
    pass

# ----------------- DATABASE HELPERS -----------------
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"unban_monitors": {}, "ban_monitors": {}}
    return {"unban_monitors": {}, "ban_monitors": {}}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"DB Error: {e}")

db = load_db()

# ----------------- TIME HELPERS (IST) -----------------
IST = timezone(timedelta(hours=5, minutes=30))

def get_current_time_str():
    return datetime.now(IST).strftime("%I:%M:%S %p")

def get_current_date_str():
    return datetime.now(IST).strftime("%d %b, %Y")

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

# ----------------- ACCURATE LIVE DETAILS CHECKER -----------------
def get_instagram_details(username):
    username = username.strip().lower().replace("@", "")
    ds_user_id = INSTAGRAM_SESSION_ID.split(":")[0] if ":" in INSTAGRAM_SESSION_ID else ""

    # Method 1: Mobile API (Best for Exact Numbers)
    try:
        url = f"https://i.instagram.com/api/v1/users/{username}/usernameinfo/"
        headers = {
            "User-Agent": "Instagram 278.0.0.19.115 Android (33/13; 440dpi; 1080x2400; Xiaomi; Redmi Note 12; sweet; qcom; en_US; 458229237)",
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}; ds_user_id={ds_user_id};",
            "X-IG-App-ID": "936619743392459"
        }
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            user = res.json().get("user", {})
            if user:
                followers = user.get("follower_count")
                following = user.get("following_count")
                return {
                    "active": True,
                    "followers": f"{followers:,}" if isinstance(followers, int) else str(followers),
                    "following": f"{following:,}" if isinstance(following, int) else str(following)
                }
        elif res.status_code == 404:
            return {"active": False, "followers": "0", "following": "0"}
    except Exception:
        pass

    # Method 2: Web Profile Info API Layer
    try:
        web_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        web_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "x-ig-app-id": "936619743392459",
            "Referer": f"https://www.instagram.com/{username}/",
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}; ds_user_id={ds_user_id};"
        }
        w_res = requests.get(web_url, headers=web_headers, timeout=8)
        if w_res.status_code == 200:
            u_data = w_res.json().get("data", {}).get("user")
            if u_data:
                f_by = u_data.get("edge_followed_by", {}).get("count", 0)
                f_to = u_data.get("edge_follow", {}).get("count", 0)
                return {
                    "active": True,
                    "followers": f"{f_by:,}",
                    "following": f"{f_to:,}"
                }
            return {"active": False, "followers": "0", "following": "0"}
        elif w_res.status_code == 404:
            return {"active": False, "followers": "0", "following": "0"}
    except Exception:
        pass

    # Method 3: Meta oEmbed Verification Fallback
    try:
        oembed_url = f"https://api.instagram.com/oembed/?url=https://www.instagram.com/{username}/"
        r = requests.get(oembed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code == 200:
            return {"active": True, "followers": "Active", "following": "Active"}
        elif r.status_code == 404:
            return {"active": False, "followers": "0", "following": "0"}
    except Exception:
        pass

    return {"active": False, "followers": "0", "following": "0"}

# ----------------- BACKGROUND MONITOR LOOP -----------------
def monitor_loop():
    while True:
        try:
            _verify_integrity()

            # 1. Unban (/ub) Check
            unban_list = list(db.get("unban_monitors", {}).items())
            for username, info in unban_list:
                status = get_instagram_details(username)
                if status["active"] is True:
                    elapsed = time.time() - info.get("start_time", time.time())
                    time_str = format_time_taken(elapsed)
                    req_time = info.get("requested_time", "N/A")
                    req_date = info.get("requested_date", get_current_date_str())
                    unban_time = get_current_time_str()
                    user_mention = f'<a href="tg://user?id={info["user_id"]}">{info.get("user_name", "User")}</a>'

                    caption = (
                        f"⚡ <b>Instagram Account Recovered / Unbanned!</b>\n\n"
                        f"👤 <b>Target:</b> <b>@{username}</b>\n"
                        f"👥 <b>Followers:</b> <code>{status['followers']}</code> | <b>Following:</b> <code>{status['following']}</code>\n"
                        f"⏱ <b>Total Time Taken:</b> {time_str}\n"
                        f"📅 <b>Requested Date:</b> {req_date}\n"
                        f"🕒 <b>Requested Time:</b> {req_time}\n"
                        f"✅ <b>Recovered at:</b> {unban_time}\n"
                        f"👑 <b>Requested by:</b> {user_mention}\n\n"
                        f"🛡️ <i>Developed by:</i> {DEVELOPER_TAG}"
                    )

                    try:
                        sent_msg = bot.send_video(chat_id=info["chat_id"], video=UNBANNED_VIDEO, caption=caption)
                        try:
                            bot.pin_chat_message(info["chat_id"], sent_msg.message_id)
                        except Exception:
                            pass
                    except Exception:
                        try:
                            bot.send_message(chat_id=info["chat_id"], text=caption)
                        except Exception:
                            pass

                    del db["unban_monitors"][username]
                    save_db(db)

                time.sleep(2)

            # 2. Ban (/b) Check
            ban_list = list(db.get("ban_monitors", {}).items())
            for username, info in ban_list:
                status = get_instagram_details(username)
                if status["active"] is False:
                    time.sleep(3)
                    recheck = get_instagram_details(username)
                    if recheck["active"] is False:
                        elapsed = time.time() - info.get("start_time", time.time())
                        time_str = format_time_taken(elapsed)
                        req_time = info.get("requested_time", "N/A")
                        req_date = info.get("requested_date", get_current_date_str())
                        ban_time = get_current_time_str()
                        user_mention = f'<a href="tg://user?id={info["user_id"]}">{info.get("user_name", "User")}</a>'
                        followers = info.get("followers", "N/A")
                        following = info.get("following", "N/A")

                        caption = (
                            f"🚫 <b>Instagram Account Banned / Terminated!</b>\n\n"
                            f"👤 <b>Target:</b> <b>@{username}</b>\n"
                            f"👥 <b>Previous Stats:</b> Followers <code>{followers}</code> | Following <code>{following}</code>\n"
                            f"⏱ <b>Time Taken to Ban:</b> {time_str}\n"
                            f"📅 <b>Requested Date:</b> {req_date}\n"
                            f"🕒 <b>Requested Time:</b> {req_time}\n"
                            f"❌ <b>Banned at:</b> {ban_time}\n"
                            f"👑 <b>Requested by:</b> {user_mention}\n\n"
                            f"🛡️ <i>Developed by:</i> {DEVELOPER_TAG}"
                        )

                        try:
                            sent_msg = bot.send_video(chat_id=info["chat_id"], video=BANNED_VIDEO, caption=caption)
                            try:
                                bot.pin_chat_message(info["chat_id"], sent_msg.message_id)
                            except Exception:
                                pass
                        except Exception:
                            try:
                                bot.send_message(chat_id=info["chat_id"], text=caption)
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

def extract_username(message):
    args = message.text.split()
    if len(args) < 2:
        return None
    return args[1].strip().replace("@", "").lower()

# ----------------- COMMAND HANDLERS -----------------
@bot.message_handler(commands=['start'])
def handle_start(message):
    _verify_integrity()
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "User"
    user_mention = f'<a href="tg://user?id={user_id}">{user_name}</a>'

    welcome_text = (
        f"👋 <b>Welcome {user_mention}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User Name:</b> {user_name}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Available Commands:</b>\n"
        f"• <code>/ub &lt;username&gt;</code> — Monitor account for recovery / unban\n"
        f"• <code>/b &lt;username&gt;</code> — Monitor account for ban\n"
        f"• <code>/status</code> — View active monitored accounts\n"
        f"• <code>/owner</code> — Developer & Credits\n"
        f"• <code>/help</code> — Bot instructions & guide\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Developer:</b> {DEVELOPER_TAG}"
    )
    bot.reply_to(message, welcome_text)

# ----------------- /owner COMMAND -----------------
@bot.message_handler(commands=['owner', 'credits', 'creator'])
def handle_owner(message):
    _verify_integrity()
    owner_text = (
        f"👑 <b>Bot Ownership & Credits</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠 <b>Author / Developer:</b> {DEVELOPER_TAG}\n"
        f"🌐 <b>Network:</b> {DEV_CHANNEL}\n"
        f"⚡ <b>System:</b> Real-time Dual Instagram Monitor\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>All rights reserved. Code protected by integrity locks.</i>"
    )
    bot.reply_to(message, owner_text)

# ----------------- /ub COMMAND -----------------
@bot.message_handler(commands=['ub', 'unban', 'm'])
def handle_unban_request(message):
    username = extract_username(message)
    user_mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name or "User"}</a>'
    
    if not username:
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/ub username</code>\n<b>Example:</b> <code>/ub fvowl</code>")
        return

    if username in db.get("unban_monitors", {}):
        bot.reply_to(message, f"ℹ️ <b>@{username}</b> is already in the unban monitoring list.")
        return

    status = get_instagram_details(username)
    if status["active"] is True:
        bot.reply_to(
            message,
            f"⚠️ <b>Request Denied:</b> <b>@{username}</b> is already <b>Active / Unbanned</b> on Instagram.\n\n"
            f"👥 <b>Followers:</b> <code>{status['followers']}</code> | <b>Following:</b> <code>{status['following']}</code>\n"
            f"👤 <b>Requested by:</b> {user_mention}"
        )
        return

    req_time = get_current_time_str()
    req_date = get_current_date_str()

    db.setdefault("unban_monitors", {})[username] = {
        "chat_id": message.chat.id,
        "user_id": message.from_user.id,
        "user_name": message.from_user.first_name or "User",
        "start_time": time.time(),
        "requested_time": req_time,
        "requested_date": req_date
    }
    save_db(db)

    caption = (
        f"🔍 <b>Instagram Account Monitoring (Recovery)</b>\n\n"
        f"👤 <b>Target:</b> <b>@{username}</b> added successfully.\n"
        f"⚡ You will receive an instant alert with full stats as soon as the account is recovered.\n\n"
        f"📅 <b>Date:</b> {req_date}\n"
        f"🕒 <b>Requested at:</b> {req_time}\n"
        f"👑 <b>Requested by:</b> {user_mention}\n\n"
        f"🛡️ <i>Powered by:</i> {DEVELOPER_TAG}"
    )

    try:
        bot.send_video(chat_id=message.chat.id, video=MONITORING_VIDEO, caption=caption, reply_to_message_id=message.message_id)
    except Exception:
        bot.send_message(chat_id=message.chat.id, text=caption, reply_to_message_id=message.message_id)

# ----------------- /b COMMAND -----------------
@bot.message_handler(commands=['b', 'ban'])
def handle_ban_request(message):
    username = extract_username(message)
    user_mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name or "User"}</a>'
    
    if not username:
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/b username</code>\n<b>Example:</b> <code>/b fvowl</code>")
        return

    if username in db.get("ban_monitors", {}):
        bot.reply_to(message, f"ℹ️ <b>@{username}</b> is already in the ban monitoring list.")
        return

    status = get_instagram_details(username)
    if status["active"] is False:
        bot.reply_to(
            message,
            f"⚠️ <b>Request Denied:</b> <b>@{username}</b> is <b>Already Banned / Unavailable</b> on Instagram.\n\n"
            f"👤 <b>Requested by:</b> {user_mention}"
        )
        return

    req_time = get_current_time_str()
    req_date = get_current_date_str()

    db.setdefault("ban_monitors", {})[username] = {
        "chat_id": message.chat.id,
        "user_id": message.from_user.id,
        "user_name": message.from_user.first_name or "User",
        "followers": status["followers"],
        "following": status["following"],
        "start_time": time.time(),
        "requested_time": req_time,
        "requested_date": req_date
    }
    save_db(db)

    caption = (
        f"🎯 <b>Instagram Account Monitoring (Ban)</b>\n\n"
        f"👤 <b>Target:</b> <b>@{username}</b> added successfully.\n"
        f"👥 <b>Current Stats:</b> Followers <code>{status['followers']}</code> | Following <code>{status['following']}</code>\n"
        f"⚡ You will be notified the instant the account gets banned.\n\n"
        f"📅 <b>Date:</b> {req_date}\n"
        f"🕒 <b>Requested at:</b> {req_time}\n"
        f"👑 <b>Requested by:</b> {user_mention}\n\n"
        f"🛡️ <i>Powered by:</i> {DEVELOPER_TAG}"
    )

    try:
        bot.send_video(chat_id=message.chat.id, video=MONITORING_VIDEO, caption=caption, reply_to_message_id=message.message_id)
    except Exception:
        bot.send_message(chat_id=message.chat.id, text=caption, reply_to_message_id=message.message_id)

# ----------------- /status COMMAND -----------------
@bot.message_handler(commands=['status', 's'])
def handle_status(message):
    unbans = db.get("unban_monitors", {})
    bans = db.get("ban_monitors", {})

    if not unbans and not bans:
        bot.reply_to(message, "📭 No accounts are currently being monitored.")
        return

    lines = ["📊 <b>Active Instagram Monitors:</b>\n━━━━━━━━━━━━━━━━━━━━"]
    if unbans:
        lines.append("\n🟢 <b>Awaiting Recovery / Unban:</b>")
        for u, d in unbans.items():
            t = format_time_taken(time.time() - d["start_time"])
            lines.append(f"• <b>@{u}</b> (Elapsed: <code>{t}</code>) — by {d.get('user_name')}")

    if bans:
        lines.append("\n🔴 <b>Awaiting Ban:</b>")
        for u, d in bans.items():
            t = format_time_taken(time.time() - d["start_time"])
            f_count = d.get("followers", "N/A")
            lines.append(f"• <b>@{u}</b> (Followers: <code>{f_count}</code> | Elapsed: <code>{t}</code>) — by {d.get('user_name')}")

    lines.append(f"\n👑 <i>System:</i> {DEVELOPER_TAG}")
    bot.reply_to(message, "\n".join(lines))

# ----------------- /help COMMAND -----------------
@bot.message_handler(commands=['help', 'h'])
def handle_help(message):
    help_text = (
        "⚙️ <b>Bot Help & Command Guide:</b>\n\n"
        "• <code>/ub &lt;username&gt;</code> — Monitor account for recovery / unban\n"
        "• <code>/b &lt;username&gt;</code> — Monitor account for ban\n"
        "• <code>/status</code> — Check all active monitors\n"
        "• <code>/owner</code> — Developer credentials & credits\n"
        "• <code>/help</code> — Show this guide\n\n"
        f"👑 <b>Author:</b> {DEVELOPER_TAG}"
    )
    bot.reply_to(message, help_text)

# ----------------- POLLING WITH AUTO-RECOVER -----------------
def run_bot_polling():
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=15, skip_pending=True)
        except Exception as e:
            print(f"[POLLING RECOVER] Connection dropped: {e}. Reconnecting in 3 seconds...")
            time.sleep(3)

if __name__ == "__main__":
    _verify_integrity()
    print(f"Dual Tracker Bot by {DEVELOPER_TAG} is active...")
    run_bot_polling()
