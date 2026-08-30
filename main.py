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

# Anime Direct MP4 Clips
MONITORING_VIDEO = "https://assets.mixkit.co/videos/preview/mixkit-digital-animation-of-screens-996-large.mp4"
UNBANNED_VIDEO = "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-background-1610-large.mp4"
BANNED_VIDEO = "https://assets.mixkit.co/videos/preview/mixkit-glitch-screen-effect-28795-large.mp4"
# --------------------------------------------------

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

try:
    bot.set_my_commands([
        types.BotCommand("ub", "Monitor account for recovery / unban"),
        types.BotCommand("b", "Monitor account for ban"),
        types.BotCommand("status", "Show active monitored accounts"),
        types.BotCommand("owner", "Developer & Credits"),
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

# ----------------- ROBUST USERNAME PARSER -----------------
def extract_username(message):
    if not message.text:
        return None
    parts = message.text.split()
    if len(parts) < 2:
        return None
    raw_user = parts[1].strip().lower().replace("@", "")
    # Clean validation for letter + number + dots + underscores
    clean = re.sub(r'[^a-z0-9._]', '', raw_user)
    return clean if clean else None

# ----------------- BULLETPROOF LIVE DETAILS CHECKER -----------------
def get_instagram_details(username):
    ds_user_id = INSTAGRAM_SESSION_ID.split(":")[0] if ":" in INSTAGRAM_SESSION_ID else ""

    # Method 1: Web Profile Info GraphQL API
    try:
        web_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "x-ig-app-id": "936619743392459",
            "Referer": f"https://www.instagram.com/{username}/",
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}; ds_user_id={ds_user_id};"
        }
        res = requests.get(web_url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("data", {}).get("user")
            if data:
                f_by = data.get("edge_followed_by", {}).get("count", 0)
                f_to = data.get("edge_follow", {}).get("count", 0)
                return {
                    "active": True,
                    "followers": f"{f_by:,}",
                    "following": f"{f_to:,}"
                }
        elif res.status_code == 404:
            return {"active": False, "followers": "0", "following": "0"}
    except Exception:
        pass

    # Method 2: Mobile App Internal API
    try:
        app_url = f"https://i.instagram.com/api/v1/users/{username}/usernameinfo/"
        app_headers = {
            "User-Agent": "Instagram 300.0.0.29.110 Android (33/13; 440dpi; 1080x2400; Xiaomi; sweet; en_US; 514229237)",
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}; ds_user_id={ds_user_id};",
            "X-IG-App-ID": "936619743392459"
        }
        res2 = requests.get(app_url, headers=app_headers, timeout=8)
        if res2.status_code == 200:
            user = res2.json().get("user", {})
            if user:
                f_by = user.get("follower_count", 0)
                f_to = user.get("following_count", 0)
                return {
                    "active": True,
                    "followers": f"{f_by:,}" if isinstance(f_by, int) else str(f_by),
                    "following": f"{f_to:,}" if isinstance(f_to, int) else str(f_to)
                }
        elif res2.status_code == 404:
            return {"active": False, "followers": "0", "following": "0"}
    except Exception:
        pass

    # Method 3: Meta oEmbed Verification Layer
    try:
        oembed_url = f"https://api.instagram.com/oembed/?url=https://www.instagram.com/{username}/"
        r = requests.get(oembed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        if r.status_code == 200:
            return {"active": True, "followers": "Active Account", "following": "Active Account"}
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

            # 1. Unban (/ub) Checking
            unban_list = list(db.get("unban_monitors", {}).items())
            for username, info in unban_list:
                status = get_instagram_details(username)
                if status["active"] is True:
                    elapsed = time.time() - info.get("start_time", time.time())
                    time_str = format_time_taken(elapsed)
                    req_time = info.get("requested_time", "N/A")
                    req_date = info.get("requested_date", get_current_date_str())
                    unban_time = get_current_time_str()
                    user_name = info.get("user_name", "User")

                    caption = (
                        "⚡ Instagram Account Recovered / Unbanned!\n\n"
                        f"👤 Target: @{username}\n"
                        f"👥 Followers: {status['followers']} | Following: {status['following']}\n"
                        f"⏱ Total Time Taken: {time_str}\n"
                        f"📅 Requested Date: {req_date}\n"
                        f"🕒 Requested Time: {req_time}\n"
                        f"✅ Recovered at: {unban_time}\n"
                        f"👑 Requested by: {user_name}\n\n"
                        f"🛡️ Developed by: {DEVELOPER_TAG}"
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

            # 2. Ban (/b) Checking
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
                        user_name = info.get("user_name", "User")
                        followers = info.get("followers", "N/A")
                        following = info.get("following", "N/A")

                        caption = (
                            "🚫 Instagram Account Banned / Terminated!\n\n"
                            f"👤 Target: @{username}\n"
                            f"👥 Previous Stats: Followers {followers} | Following {following}\n"
                            f"⏱ Time Taken to Ban: {time_str}\n"
                            f"📅 Requested Date: {req_date}\n"
                            f"🕒 Requested Time: {req_time}\n"
                            f"❌ Banned at: {ban_time}\n"
                            f"👑 Requested by: {user_name}\n\n"
                            f"🛡️ Developed by: {DEVELOPER_TAG}"
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

# ----------------- COMMAND HANDLERS -----------------
@bot.message_handler(commands=['start'])
def handle_start(message):
    _verify_integrity()
    user_name = message.from_user.first_name or "User"
    user_id = message.from_user.id

    welcome_text = (
        f"👋 Welcome {user_name}!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User Name: {user_name}\n"
        f"🆔 User ID: {user_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Available Commands:\n"
        f"• /ub <username> — Monitor account for recovery / unban\n"
        f"• /b <username> — Monitor account for ban\n"
        f"• /status — View active monitored accounts\n"
        f"• /owner — Developer & Credits\n"
        f"• /help — Bot instructions & guide\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 Developer: {DEVELOPER_TAG}"
    )
    bot.reply_to(message, welcome_text)

# ----------------- /owner COMMAND -----------------
@bot.message_handler(commands=['owner', 'credits', 'creator'])
def handle_owner(message):
    _verify_integrity()
    owner_text = (
        f"👑 Bot Ownership & Credits\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠 Author / Developer: {DEVELOPER_TAG}\n"
        f"🌐 Network: {DEV_CHANNEL}\n"
        f"⚡ System: Real-time Instagram Dual Monitor\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"All rights reserved. Code protected by integrity locks."
    )
    bot.reply_to(message, owner_text)

# ----------------- /ub COMMAND (UNBAN MONITOR) -----------------
@bot.message_handler(commands=['ub', 'unban', 'm'])
def handle_unban_request(message):
    username = extract_username(message)
    user_name = message.from_user.first_name or "User"
    
    if not username:
        bot.reply_to(message, "⚠️ Usage: /ub username\nExample: /ub ambient.rot")
        return

    if username in db.get("unban_monitors", {}):
        bot.reply_to(message, f"ℹ️ @{username} is already in the unban monitoring list.")
        return

    status = get_instagram_details(username)
    # If account is already active, deny monitoring request
    if status["active"] is True:
        bot.reply_to(
            message,
            f"⚠️ Request Denied: @{username} is already Active / Unbanned on Instagram.\n\n"
            f"👥 Followers: {status['followers']} | Following: {status['following']}\n"
            f"👤 Requested by: {user_name}"
        )
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
        "🔍 Instagram Account Monitoring (Recovery)\n\n"
        f"👤 Target: @{username} added successfully.\n"
        f"⚡ You will receive an instant alert with full stats as soon as the account is recovered.\n\n"
        f"📅 Date: {req_date}\n"
        f"🕒 Requested at: {req_time}\n"
        f"👑 Requested by: {user_name}\n\n"
        f"🛡️ Powered by: {DEVELOPER_TAG}"
    )

    try:
        bot.send_video(chat_id=message.chat.id, video=MONITORING_VIDEO, caption=caption, reply_to_message_id=message.message_id)
    except Exception:
        bot.send_message(chat_id=message.chat.id, text=caption, reply_to_message_id=message.message_id)

# ----------------- /b COMMAND (BAN MONITOR) -----------------
@bot.message_handler(commands=['b', 'ban'])
def handle_ban_request(message):
    username = extract_username(message)
    user_name = message.from_user.first_name or "User"
    
    if not username:
        bot.reply_to(message, "⚠️ Usage: /b username\nExample: /b ambient.rot")
        return

    if username in db.get("ban_monitors", {}):
        bot.reply_to(message, f"ℹ️ @{username} is already in the ban monitoring list.")
        return

    status = get_instagram_details(username)
    # If account is already banned / unavailable, deny ban request
    if status["active"] is False:
        bot.reply_to(
            message,
            f"⚠️ Request Denied: @{username} is already Banned / Unavailable on Instagram.\n\n"
            f"👤 Requested by: {user_name}"
        )
        return

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
        "🎯 Instagram Account Monitoring (Ban)\n\n"
        f"👤 Target: @{username} added successfully.\n"
        f"👥 Current Stats: Followers {status['followers']} | Following {status['following']}\n"
        f"⚡ You will be notified the instant the account gets banned.\n\n"
        f"📅 Date: {req_date}\n"
        f"🕒 Requested at: {req_time}\n"
        f"👑 Requested by: {user_name}\n\n"
        f"🛡️ Powered by: {DEVELOPER_TAG}"
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

    lines = ["📊 Active Instagram Monitors:\n━━━━━━━━━━━━━━━━━━━━"]
    if unbans:
        lines.append("\n🟢 Awaiting Recovery / Unban:")
        for u, d in unbans.items():
            t = format_time_taken(time.time() - d["start_time"])
            lines.append(f"• @{u} (Elapsed: {t}) — by {d.get('user_name')}")

    if bans:
        lines.append("\n🔴 Awaiting Ban:")
        for u, d in bans.items():
            t = format_time_taken(time.time() - d["start_time"])
            f_count = d.get("followers", "N/A")
            lines.append(f"• @{u} (Followers: {f_count} | Elapsed: {t}) — by {d.get('user_name')}")

    lines.append(f"\n👑 System: {DEVELOPER_TAG}")
    bot.reply_to(message, "\n".join(lines))

# ----------------- /help COMMAND -----------------
@bot.message_handler(commands=['help', 'h'])
def handle_help(message):
    help_text = (
        "⚙️ Bot Help & Command Guide:\n\n"
        "• /ub <username> — Monitor account for recovery / unban\n"
        "• /b <username> — Monitor account for ban\n"
        "• /status — Check all active monitors\n"
        "• /owner — Developer credentials & credits\n"
        "• /help — Show this guide\n\n"
        f"👑 Author: {DEVELOPER_TAG}"
    )
    bot.reply_to(message, help_text)

# ----------------- POLLING WITH AUTO-RECONNECT -----------------
def run_bot_polling():
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=15, skip_pending=True)
        except Exception as e:
            print(f"[POLLING RECOVER] Connection error: {e}. Reconnecting in 3s...")
            time.sleep(3)

if __name__ == "__main__":
    _verify_integrity()
    print(f"Dual Tracker Bot by {DEVELOPER_TAG} is active...")
    run_bot_polling()
