import os
import sys
import time
import json
import re
import threading
import io
import base64
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
from datetime import datetime, timezone, timedelta

# Force unbuffered stdout for Render logs
sys.stdout.reconfigure(line_buffering=True)

# ----------------- TAMPER-PROOF CREDITS -----------------
DEVELOPER_TAG = "@jyoex"
DEV_CHANNEL = "JYOEX NETWORK"

def _verify_integrity():
    if DEVELOPER_TAG != "@jyoex" or DEV_CHANNEL != "JYOEX NETWORK":
        print("[SECURITY] Tamper detected.", flush=True)
        sys.exit(1)

_verify_integrity()

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
        print(f"Web server active on port {port}", flush=True)
        server.serve_forever()
    except Exception as e:
        print(f"Web server error: {e}", flush=True)

threading.Thread(target=run_server, daemon=True).start()

# ----------------- CONFIGURATION -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8961164126:AAG_Q249Bw2m4lOlcVzB2XymhpSyHTvP1SU")
INSTAGRAM_SESSION_ID = os.environ.get("INSTAGRAM_SESSION_ID", "70229745656:sLSyRu4K1KDgPw:11:AYg1H4LDg5LXUI5a3y8ebDWyAoexZ0jKncnz-WcYvA")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

ALLOWED_CLAIM_PASSWORDS = ["mansour$vx", "Hamzai@1"]
AUTHORIZED_OFFICIAL_GROUPS = ["comchater"]
CHECK_INTERVAL_SECONDS = 15
DB_FILE = "dual_tracker_db.json"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", disable_web_page_preview=True)

admin_state = {}
user_message_history = {}

# ----------------- GITHUB DATABASE SYNC ENGINE -----------------
def load_from_github():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DB_FILE}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            file_data = res.json()
            if "content" in file_data:
                decoded = base64.b64decode(file_data["content"])
                with open(DB_FILE, "wb") as f:
                    f.write(decoded)
                print("✅ Successfully synced database from GitHub!", flush=True)
                return True
    except Exception as e:
        print(f"GitHub Load Error: {e}", flush=True)
    return False

def sync_to_github():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return
    try:
        if not os.path.exists(DB_FILE):
            return
        with open(DB_FILE, "rb") as f:
            content_bytes = f.read()
        content_encoded = base64.b64encode(content_bytes).decode("utf-8")

        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DB_FILE}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        
        get_res = requests.get(api_url, headers=headers, timeout=10)
        sha = None
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")

        data_payload = {
            "message": "Auto-update database [skip ci]",
            "content": content_encoded,
            "branch": "main"
        }
        if sha:
            data_payload["sha"] = sha

        put_res = requests.put(api_url, headers=headers, json=data_payload, timeout=10)
        if put_res.status_code not in [200, 201]:
            data_payload["branch"] = "master"
            requests.put(api_url, headers=headers, json=data_payload, timeout=10)
    except Exception as e:
        print(f"GitHub Sync Error: {e}", flush=True)

# ----------------- DATABASE LOADER & SAVER -----------------
def get_default_db_data():
    return {
        "_id": "global_config",
        "unban_monitors": {},
        "ban_monitors": {},
        "admins": [],
        "users": {},
        "groups": [],
        "settings": {
            "maintenance": False,
            "new_user_notify": True
        },
        "stats": {
            "total_monitored": 0
        },
        "channels": [
            {"id": "c1", "name": "Jyoex", "tag": "@jyoex", "link": "https://t.me/jyoex", "color": "📢"},
            {"id": "c2", "name": "Comchater", "tag": "@Comchater", "link": "https://t.me/Comchater", "color": "📢"},
            {"id": "c3", "name": "Sell Hub", "tag": "@Foraremy", "link": "https://t.me/+gM43iG6v-vFmYjc1", "color": "📢"}
        ],
        "media": {
            "force_join": {
                "type": "animation",
                "id": "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUyemw2YjhhNWx5endhbGl5cmZ6dmJrYXhmNDZ0bDFmbmhwZmszNHd0eiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/1cGfefKF0bSSmzyThu/giphy.gif"
            },
            "dm_notice": {
                "type": "animation",
                "id": "https://media4.giphy.com/media/v1.Y2lkPTZjMDliOTUyYW1jdmFrdDN2anZ3a2t0cWZna2xjNG5tYWxxZWp2cWJwOWh0bno3NiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xWIklyBVywrEjcMKWJ/giphy.gif"
            },
            "subscription": {
                "type": "animation",
                "id": "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUycW84MGMwMjE4ZXdjOGpnMmhlaHVqYjIzaTR2c2FzZzY4cHBqNnN1aSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7aCQtmuE6a5VybLi/giphy.gif"
            },
            "ub_req": {
                "type": "animation",
                "id": "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUyZTcyYTVjaGc4NmY1emdwNWo3bHZjdHdjejc5ZTV6a2dtdmZ0cDVpdyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/FB5EOw0CaaQM0/giphy.gif"
            },
            "ub_done": {
                "type": "animation",
                "id": "https://media3.giphy.com/media/v1.Y2lkPTZjMDliOTUycDhtZ2lpcTJqcGoxam9rM2k3cDd1Z2Vpc2hteWdxZzR5NHF1amFkYiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/bdrGSR9rPkvEoRp8dw/giphy.gif"
            },
            "b_req": {
                "type": "animation",
                "id": "https://media2.giphy.com/media/v1.Y2lkPTZjMDliOTUya2FmcnV4OWd5azI1NzhnMzZicG5mOHhrZmFzNHFlMW5zaTJuYXFkNiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/HyOOyynWxMxig/giphy.gif"
            },
            "b_done": {
                "type": "animation",
                "id": "https://media1.giphy.com/media/v1.Y2lkPTZjMDliOTUydjNzdzh1NjBhcHp0bTdvNzJmcmdjZjhseHE4c3Nqd21waHR2dGd5byZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/XOiECsEvO6PfVkEJ3P/giphy.gif"
            },
            "deny": {
                "type": "animation",
                "id": "https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUyZXA5MmJ6ZDFjMHc0MmZ5bTJ0ZXNqeTIxbjJpenc4bWJtcXdpcWJuZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/33OJOxsSqv6uPVOUcA/giphy.gif"
            }
        }
    }

def load_db():
    default_data = get_default_db_data()
    load_from_github()
    
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_data.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return default_data
    return default_data

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, default=str)
        sync_to_github()
    except Exception as e:
        print(f"Local DB Error: {e}", flush=True)

db = load_db()

# ----------------- HELPERS -----------------
IST = timezone(timedelta(hours=5, minutes=30))

def get_current_time_str():
    return datetime.now(IST).strftime("%I:%M %p")

def get_current_date_str():
    return datetime.now(IST).strftime("%d %b, %Y")

def get_full_timestamp():
    return datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")

def get_user_mention(user_id, first_name):
    clean_name = first_name.replace("<", "").replace(">", "") if first_name else "User"
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'

def get_ig_link(username):
    clean_user = username.strip().replace("@", "")
    return f'<a href="https://instagram.com/{clean_user}">@{clean_user}</a>'

def is_admin_or_owner(user_id):
    return user_id in db.get("admins", [])

def register_user(user, chat_id=None):
    user_id = str(user.id)
    is_new = user_id not in db.get("users", {})

    if is_new:
        db.setdefault("users", {})[user_id] = {
            "id": user.id,
            "name": user.first_name or "Unknown",
            "username": f"@{user.username}" if user.username else "No Username",
            "joined_at": get_full_timestamp(),
            "req_count": 0
        }
        save_db(db)

        if db.get("settings", {}).get("new_user_notify", True):
            mention = get_user_mention(user.id, user.first_name)
            u_tag = f'<a href="tg://user?id={user.id}">@{user.username}</a>' if user.username else "<i>None</i>"
            alert_text = (
                "🆕 <b>New User Alert:</b>\n\n"
                f"👤 <b>Name:</b> {mention}\n"
                f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
                f"🔗 <b>Username:</b> {u_tag}\n"
                f"📅 <b>Date & Time:</b> <code>{get_full_timestamp()}</code>"
            )
            for adm in db.get("admins", []):
                try:
                    bot.send_message(adm, alert_text, protect_content=True)
                except Exception:
                    pass
    else:
        db["users"][user_id]["name"] = user.first_name or "Unknown"
        db["users"][user_id]["username"] = f"@{user.username}" if user.username else "No Username"
        save_db(db)

    if chat_id and chat_id not in db.get("groups", []):
        if chat_id < 0:
            db.setdefault("groups", []).append(chat_id)
            save_db(db)

def track_and_clean_spam(chat_id, user_id, message_id):
    if chat_id < 0:
        return
    history = user_message_history.setdefault(user_id, [])
    history.append(message_id)
    if len(history) >= 3:
        oldest = history.pop(0)
        try:
            bot.delete_message(chat_id=chat_id, message_id=oldest)
        except Exception:
            pass

def auto_delete_after_delay(chat_id, message_id, delay_seconds=300):
    def delete_worker():
        time.sleep(delay_seconds)
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
    threading.Thread(target=delete_worker, daemon=True).start()

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
def send_custom_media(chat_id, key, caption, reply_to=None, reply_markup=None):
    media_data = db.get("media", {}).get(key)
    is_protected = True if chat_id > 0 else False

    if not media_data:
        return bot.send_message(chat_id=chat_id, text=caption, reply_to_message_id=reply_to, reply_markup=reply_markup, protect_content=is_protected)

    if isinstance(media_data, str):
        m_type = "animation" if media_data.endswith(".gif") else "photo"
        m_id = media_data
    else:
        m_type = media_data.get("type", "photo")
        m_id = media_data.get("id", "")

    try:
        if m_type == "video":
            return bot.send_video(chat_id=chat_id, video=m_id, caption=caption, reply_to_message_id=reply_to, reply_markup=reply_markup, protect_content=is_protected)
        elif m_type == "animation":
            return bot.send_animation(chat_id=chat_id, animation=m_id, caption=caption, reply_to_message_id=reply_to, reply_markup=reply_markup, protect_content=is_protected)
        elif m_type == "photo":
            return bot.send_photo(chat_id=chat_id, photo=m_id, caption=caption, reply_to_message_id=reply_to, reply_markup=reply_markup, protect_content=is_protected)
        else:
            return bot.send_photo(chat_id=chat_id, photo=m_id, caption=caption, reply_to_message_id=reply_to, reply_markup=reply_markup, protect_content=is_protected)
    except Exception as e:
        print(f"Media fallback error: {e}", flush=True)
        return bot.send_message(chat_id=chat_id, text=caption, reply_to_message_id=reply_to, reply_markup=reply_markup, protect_content=is_protected)

# ----------------- STRICT FORCE JOIN VERIFICATION -----------------
def get_missing_channels(user_id):
    missing = []
    for ch in db.get("channels", []):
        try:
            member = bot.get_chat_member(ch["tag"], user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                missing.append(ch)
        except Exception:
            pass
    return missing

def build_force_join_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in db.get("channels", []):
        btn_label = f"{ch.get('color', '📢')} {ch['name']}"
        markup.add(types.InlineKeyboardButton(btn_label, url=ch["link"]))
    markup.add(types.InlineKeyboardButton("✅ Verify", callback_data="verify_channels"))
    return markup

def check_access(message):
    user = message.from_user
    chat = message.chat
    register_user(user, chat.id)
    track_and_clean_spam(chat.id, user.id, message.message_id)

    if is_admin_or_owner(user.id):
        return True

    missing = get_missing_channels(user.id)
    if missing:
        mention = get_user_mention(user.id, user.first_name)
        text = (
            "⚠️ <b>Access Restricted</b>\n\n"
            f"Hello {mention}, you must join all our required official channels below to access this bot:\n\n"
            "<i>Click each channel to join, then tap Verify:</i>"
        )
        send_custom_media(chat.id, "force_join", text, reply_to=message.message_id, reply_markup=build_force_join_markup())
        return False

    if db.get("settings", {}).get("maintenance", False):
        maintenance_msg = (
            "🛠 <b>System Maintenance Notice</b>\n\n"
            "Our servers are currently undergoing scheduled upgrades.\n"
            "All monitoring requests are temporarily paused."
        )
        bot.reply_to(message, maintenance_msg, protect_content=(chat.id > 0))
        return False

    if chat.type == "private":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Comchater", url="https://t.me/Comchater"))
        mention = get_user_mention(user.id, user.first_name)
        notice_text = (
            "ℹ️ <b>Community Only Bot</b>\n\n"
            f"Hello {mention},\n"
            "To ensure 24/7 high-speed live monitoring, all bot services are hosted inside our official discussion group."
        )
        send_custom_media(chat.id, "dm_notice", notice_text, reply_to=message.message_id, reply_markup=markup)
        return False

    return True

@bot.callback_query_handler(func=lambda call: call.data == "verify_channels")
def handle_verify_callback(call):
    missing = get_missing_channels(call.from_user.id)
    if missing:
        bot.answer_callback_query(call.id, "❌ You haven't joined all channels yet!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "✅ Verified! You can now use the bot in @Comchater", show_alert=True)
        try:
            bot.edit_message_caption(
                caption="✅ <b>Access Granted!</b> You are verified. You can now use commands inside <b>@Comchater</b>.",
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

            if is_admin_or_owner(message.from_user.id):
                return

            try:
                bot.send_message(message.chat.id, "<b>Unauthorized Group</b>\n\nThis bot only works inside @Comchater.\nLeaving now...")
                bot.leave_chat(message.chat.id)
            except Exception:
                pass

# ----------------- INSTAGRAM MULTI-GATEWAY ENGINE -----------------
def get_instagram_details(username):
    username = username.strip().lower().replace("@", "")
    ds_user_id = INSTAGRAM_SESSION_ID.split(":")[0] if ":" in INSTAGRAM_SESSION_ID else ""

    try:
        web_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 324.0.0.18.113",
            "x-ig-app-id": "936619743392459",
            "Referer": f"https://www.instagram.com/{username}/",
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}; ds_user_id={ds_user_id};"
        }
        res = requests.get(web_url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", {}).get("user")
            if data and "username" in data:
                return {
                    "active": True,
                    "followers": data.get("edge_followed_by", {}).get("count", 0),
                    "following": data.get("edge_follow", {}).get("count", 0)
                }
            return {"active": False, "followers": 0, "following": 0}
        elif res.status_code == 404:
            return {"active": False, "followers": 0, "following": 0}
    except Exception:
        pass

    try:
        oembed_url = f"https://api.instagram.com/oembed/?url=https://www.instagram.com/{username}/"
        res_o = requests.get(oembed_url, timeout=5)
        if res_o.status_code == 200:
            return {"active": True, "followers": "N/A", "following": "N/A"}
        elif res_o.status_code == 404:
            return {"active": False, "followers": 0, "following": 0}
    except Exception:
        pass

    try:
        app_url = f"https://i.instagram.com/api/v1/users/{username}/usernameinfo/"
        app_headers = {
            "User-Agent": "Instagram 278.0.0.19.115 Android (33/13; 440dpi; 1080x2400; Xiaomi; sweet; en_US; 458229237)",
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}; ds_user_id={ds_user_id};",
            "X-IG-App-ID": "936619743392459"
        }
        res_app = requests.get(app_url, headers=app_headers, timeout=5)
        if res_app.status_code == 200:
            u_info = res_app.json().get("user", {})
            if u_info and "username" in u_info:
                return {
                    "active": True,
                    "followers": u_info.get("follower_count", 0),
                    "following": u_info.get("following_count", 0)
                }
        elif res_app.status_code == 404:
            return {"active": False, "followers": 0, "following": 0}
    except Exception:
        pass

    return {"active": False, "followers": 0, "following": 0}

# ----------------- BACKGROUND MONITOR LOOP -----------------
def monitor_loop():
    while True:
        try:
            _verify_integrity()

            unban_list = list(db.get("unban_monitors", {}).items())
            for username, info in unban_list:
                status = get_instagram_details(username)
                if status["active"] is True:
                    elapsed = time.time() - info.get("start_time", time.time())
                    time_str = format_time_taken(elapsed)
                    f_by = format_count(status["followers"])
                    f_to = format_count(status["following"])
                    user_mention = get_user_mention(info.get("user_id"), info.get("user_name"))
                    ig_link = get_ig_link(username)

                    caption = (
                        "🎉 <b>Instagram Account Recovered</b>\n\n"
                        f"Target: <b>{ig_link}</b>\n"
                        f"Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
                        f"Time Taken: <code>{time_str}</code>\n"
                        f"Recovered at: <code>{get_current_time_str()}</code>\n\n"
                        f"👤 Requested by: {user_mention}"
                    )

                    sent_msg = send_custom_media(info["chat_id"], "ub_done", caption)
                    try:
                        bot.pin_chat_message(info["chat_id"], sent_msg.message_id)
                    except Exception:
                        pass

                    del db["unban_monitors"][username]
                    save_db(db)

                time.sleep(2)

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
                        ig_link = get_ig_link(username)

                        caption = (
                            "🚫 <b>Instagram Account Banned</b>\n\n"
                            f"Target: <b>{ig_link}</b>\n"
                            f"Previous Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
                            f"Time Taken: <code>{time_str}</code>\n"
                            f"Banned at: <code>{get_current_time_str()}</code>\n\n"
                            f"👤 Requested by: {user_mention}"
                        )

                        sent_msg = send_custom_media(info["chat_id"], "b_done", caption)
                        try:
                            bot.pin_chat_message(info["chat_id"], sent_msg.message_id)
                        except Exception:
                            pass

                        del db["ban_monitors"][username]
                        save_db(db)

                time.sleep(2)

            time.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            print(f"Loop error: {e}", flush=True)
            time.sleep(10)

threading.Thread(target=monitor_loop, daemon=True).start()

# ----------------- ADMIN DASHBOARD -----------------
def get_admin_panel_markup():
    m_status = "🟢 ON" if db.get("settings", {}).get("maintenance", False) else "⚪ OFF"
    n_status = "🔔 ON" if db.get("settings", {}).get("new_user_notify", True) else "🔕 OFF"

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📬 Mailing", callback_data="admin_mailing_select"),
        types.InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
        types.InlineKeyboardButton(f"🛠 Maintenance ({m_status})", callback_data="toggle_maintenance"),
        types.InlineKeyboardButton(f"👤 New User ({n_status})", callback_data="toggle_notify"),
        types.InlineKeyboardButton("🖼 Manage Media", callback_data="admin_media"),
        types.InlineKeyboardButton("🔘 Customize Buttons", callback_data="admin_btn_menu"),
        types.InlineKeyboardButton("👥 Manage Admins", callback_data="admin_manage"),
        types.InlineKeyboardButton("❌ Close Panel", callback_data="admin_close")
    )
    return markup

@bot.message_handler(commands=['claim'])
def handle_claim(message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if is_admin_or_owner(user_id):
        bot.reply_to(message, "👑 You are already authorized as Admin. Send <code>/admin</code> to open panel.")
        return

    admin_state[user_id] = "waiting_claim_password"
    bot.reply_to(message, "🔒 <b>Owner Verification Required</b>\n\nPlease enter the secret admin password:")

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    user_id = message.from_user.id
    if not is_admin_or_owner(user_id):
        bot.reply_to(message, "⛔ <b>Access Denied:</b> Send <code>/claim</code> to authenticate first.")
        return
    
    admin_text = (
        "🔧 <b>Administrator Control Panel</b>\n\n"
        "Welcome to the master management dashboard.\n"
        "Select an action from the options below:"
    )
    bot.reply_to(message, admin_text, reply_markup=get_admin_panel_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_") or call.data.startswith("toggle_") or call.data.startswith("set_") or call.data.startswith("btn_") or call.data.startswith("col_") or call.data.startswith("mail_"))
def handle_admin_callbacks(call):
    user_id = call.from_user.id
    if not is_admin_or_owner(user_id):
        bot.answer_callback_query(call.id, "Access Denied", show_alert=True)
        return

    data = call.data

    if data == "admin_close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if data == "admin_mailing_select":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🌐 Both (Bot Users + Groups)", callback_data="mail_target_both"),
            types.InlineKeyboardButton("👤 Bot Users Only", callback_data="mail_target_users"),
            types.InlineKeyboardButton("👥 Groups Only", callback_data="mail_target_groups"),
            types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back")
        )
        bot.edit_message_text(
            "📬 <b>Select Mailing Broadcast Target:</b>\n\n"
            "Choose where you want the broadcast message to be delivered:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    if data.startswith("mail_target_"):
        target_mode = data.replace("mail_target_", "")
        admin_state[user_id] = f"waiting_broadcast_{target_mode}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_action"))
        bot.edit_message_text(
            f"📬 <b>Broadcast Mode: ({target_mode.upper()})</b>\n\n"
            "Send or <b>FORWARD</b> the message right now.\n"
            "Supports Text, Photos, GIFs, Videos, or Files.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    if data == "admin_stats":
        total_users = len(db.get("users", {}))
        total_groups = len(db.get("groups", []))
        ub_count = len(db.get("unban_monitors", {}))
        b_count = len(db.get("ban_monitors", {}))
        total_tracked = db.get("stats", {}).get("total_monitored", 0) + ub_count + b_count
        db_mode = "GitHub JSON Auto-Sync 📁🔄"

        stats_text = (
            "📊 <b>Bot Real-time Analytics Dashboard</b>\n\n"
            f"👤 <b>Total Unique Users:</b> <code>{total_users:,}</code>\n"
            f"👥 <b>Active Registered Groups:</b> <code>{total_groups}</code>\n"
            f"⚡ <b>Awaiting Unban (/ub):</b> <code>{ub_count}</code>\n"
            f"🚫 <b>Awaiting Ban (/b):</b> <code>{b_count}</code>\n"
            f"📈 <b>Total Accounts Tracked:</b> <code>{total_tracked:,}</code>\n"
            f"💾 <b>Database Engine:</b> <code>{db_mode}</code>\n"
            f"🕒 <b>Server Status:</b> <code>Online 24/7 (Render)</code>"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📑 View All Users List", callback_data="admin_user_list"),
            types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back")
        )
        bot.edit_message_text(stats_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
        return

    if data == "admin_user_list":
        users = db.get("users", {})
        if not users:
            bot.answer_callback_query(call.id, "No users registered yet.", show_alert=True)
            return

        out = io.StringIO()
        out.write("==== REGISTERED USERS DATABASE ====\n\n")
        for uid, u in users.items():
            out.write(f"ID: {uid} | Name: {u.get('name')} | Username: {u.get('username')} | Requests: {u.get('req_count', 0)} | Joined: {u.get('joined_at')}\n")
        
        out.seek(0)
        bio = io.BytesIO(out.getvalue().encode('utf-8'))
        bio.name = f"users_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        bot.send_document(call.message.chat.id, bio, caption=f"📄 Total Registered Users: <b>{len(users)}</b>")
        bot.answer_callback_query(call.id, "Database document generated.")
        return

    if data == "toggle_maintenance":
        curr = db.setdefault("settings", {}).get("maintenance", False)
        db["settings"]["maintenance"] = not curr
        save_db(db)
        state_str = "ENABLED (ON)" if not curr else "DISABLED (OFF)"
        bot.answer_callback_query(call.id, f"Maintenance Mode {state_str}", show_alert=True)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_panel_markup())
        return

    if data == "toggle_notify":
        curr = db.setdefault("settings", {}).get("new_user_notify", True)
        db["settings"]["new_user_notify"] = not curr
        save_db(db)
        state_str = "ENABLED (ON)" if not curr else "DISABLED (OFF)"
        bot.answer_callback_query(call.id, f"New User Alert {state_str}", show_alert=True)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_panel_markup())
        return

    if data == "admin_media":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("1️⃣ /ub Request Alert GIF", callback_data="set_ub_req"),
            types.InlineKeyboardButton("2️⃣ /ub Recovered Alert GIF", callback_data="set_ub_done"),
            types.InlineKeyboardButton("3️⃣ /b Request Alert GIF", callback_data="set_b_req"),
            types.InlineKeyboardButton("4️⃣ /b Banned Alert GIF", callback_data="set_b_done"),
            types.InlineKeyboardButton("5️⃣ ⚠️ Deny Alert GIF", callback_data="set_deny"),
            types.InlineKeyboardButton("6️⃣ 🚪 DM Notice GIF", callback_data="set_dm_notice"),
            types.InlineKeyboardButton("7️⃣ 💎 Subscription Alert GIF", callback_data="set_subscription"),
            types.InlineKeyboardButton("8️⃣ 🔒 Force Join GIF", callback_data="set_force_join"),
            types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back")
        )
        bot.edit_message_text(
            "🖼 <b>Manage & Customize Media:</b>\n\nSelect any alert stage below to update its Photo/GIF/Video:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    if data.startswith("set_"):
        action = data.replace("set_", "")
        admin_state[user_id] = f"waiting_media_{action}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_action"))
        bot.edit_message_text(
            f"📸 <b>Send Media for {action}</b>\n\nPlease send the Photo, GIF, or Video right now.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    if data == "admin_btn_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in db.get("channels", []):
            markup.add(
                types.InlineKeyboardButton(f"✏️ Rename: {ch['name']}", callback_data=f"btn_name_{ch['id']}"),
                types.InlineKeyboardButton(f"🎨 Color Theme: {ch.get('color', '📢')}", callback_data=f"btn_color_{ch['id']}")
            )
        markup.add(types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        bot.edit_message_text("🔘 <b>Force Join Button Customizer</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
        return

    if data.startswith("btn_name_"):
        cid = data.replace("btn_name_", "")
        admin_state[user_id] = f"waiting_btn_name_{cid}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_action"))
        bot.edit_message_text(f"✏️ <b>Enter New Button Text for Channel ({cid}):</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
        return

    if data.startswith("btn_color_"):
        cid = data.replace("btn_color_", "")
        color_map = [("green", "🟢"), ("red", "🔴"), ("blue", "🔵"), ("yellow", "🟡"), ("purple", "🟣"), ("black", "⚫"), ("white", "⚪"), ("fire", "🔥"), ("horn", "📢")]
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(sym, callback_data=f"col_{cid}_{name}") for name, sym in color_map]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_btn_menu"))
        bot.edit_message_text(f"🎨 <b>Select Emoji for Channel ({cid}):</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
        return

    if data.startswith("col_"):
        parts = data.split("_")
        cid = parts[1]
        cname = parts[2]
        sym_dict = {"green": "🟢", "red": "🔴", "blue": "🔵", "yellow": "🟡", "purple": "🟣", "black": "⚫", "white": "⚪", "fire": "🔥", "horn": "📢"}
        chosen_symbol = sym_dict.get(cname, "📢")
        for ch in db.get("channels", []):
            if ch["id"] == cid:
                ch["color"] = chosen_symbol
                break
        save_db(db)
        bot.answer_callback_query(call.id, f"Color updated to {chosen_symbol}", show_alert=True)
        bot.edit_message_text("🔘 <b>Force Join Button Customizer</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_panel_markup())
        return

    if data == "admin_manage":
        adms = db.get("admins", [])
        adm_lines = [f"• <code>{a}</code>" for a in adms]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
        bot.edit_message_text("👥 <b>Authorized Admins:</b>\n\n" + "\n".join(adm_lines), chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
        return

    if data == "admin_back":
        bot.edit_message_text("🔧 <b>Administrator Control Panel</b>\n\nSelect an action below:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_panel_markup())
        return

@bot.callback_query_handler(func=lambda call: call.data == "cancel_action")
def handle_cancel_action(call):
    admin_state.pop(call.from_user.id, None)
    bot.answer_callback_query(call.id, "Action cancelled.")
    bot.edit_message_text("🔧 <b>Administrator Control Panel</b>\n\nSelect an action below:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_panel_markup())

@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'document', 'audio', 'voice', 'sticker'], func=lambda msg: msg.from_user.id in admin_state)
def process_admin_inputs(message):
    user_id = message.from_user.id
    state = admin_state.get(user_id)

    if state == "waiting_claim_password":
        admin_state.pop(user_id, None)
        entered_pass = message.text.strip() if message.text else ""
        if entered_pass in ALLOWED_CLAIM_PASSWORDS:
            if user_id not in db["admins"]:
                db.setdefault("admins", []).append(user_id)
                save_db(db)
            bot.reply_to(message, "👑 <b>Password Verified!</b> You are now registered as Owner/Admin. Send <code>/admin</code> to open panel.")
        else:
            bot.reply_to(message, "❌ <b>Incorrect Password!</b> Access Denied.")
        return

    if message.text and message.text.lower() in ["/cancel", "cancel"]:
        admin_state.pop(user_id, None)
        bot.reply_to(message, "❌ <b>Action Cancelled.</b>", reply_markup=get_admin_panel_markup())
        return

    if state and state.startswith("waiting_broadcast_"):
        target_mode = state.replace("waiting_broadcast_", "")
        admin_state.pop(user_id, None)
        status_msg = bot.reply_to(message, "⏳ <b>Broadcasting message...</b>")

        if target_mode == "both":
            targets = list(db.get("users", {}).keys()) + db.get("groups", [])
        elif target_mode == "users":
            targets = list(db.get("users", {}).keys())
        elif target_mode == "groups":
            targets = list(db.get("groups", []))
        else:
            targets = []

        total = len(targets)
        sent = 0
        failed = 0

        for target in targets:
            try:
                target_chat_id = int(target)
                bot.copy_message(chat_id=target_chat_id, from_chat_id=message.chat.id, message_id=message.message_id)
                sent += 1
                time.sleep(0.04)
            except Exception:
                failed += 1

        report = (
            f"✅ <b>Mailing Broadcast ({target_mode.upper()}) Completed!</b>\n\n"
            f"• <b>Total Targets:</b> <code>{total}</code>\n"
            f"• <b>Delivered Successfully:</b> <code>{sent}</code>\n"
            f"• <b>Failed / Blocked:</b> <code>{failed}</code>"
        )
        bot.edit_message_text(report, chat_id=message.chat.id, message_id=status_msg.message_id)
        return

    if state and state.startswith("waiting_btn_name_"):
        cid = state.replace("waiting_btn_name_", "")
        new_name = message.text.strip()
        for ch in db.get("channels", []):
            if ch["id"] == cid:
                ch["name"] = new_name
                break
        save_db(db)
        admin_state.pop(user_id, None)
        bot.reply_to(message, f"✅ <b>Success:</b> Button text updated to: <b>{new_name}</b>", reply_markup=get_admin_panel_markup())
        return

    if state and state.startswith("waiting_media_"):
        action = state.replace("waiting_media_", "")
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
            admin_state.pop(user_id, None)
            bot.reply_to(message, f"✅ <b>Success:</b> Media for <code>/{action}</code> updated successfully!", reply_markup=get_admin_panel_markup())
        else:
            bot.reply_to(message, "❌ Invalid media type. Please send Photo, GIF, or Video.")

@bot.message_handler(commands=['start', 'help', 'h'])
def handle_start_help(message):
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

@bot.message_handler(commands=['ub', 'unban'])
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

    ig_link = get_ig_link(username)

    if username in db.get("unban_monitors", {}):
        bot.reply_to(message, f"⚠️ <b>{ig_link}</b> is already being monitored.")
        return

    status = get_instagram_details(username)
    if status["active"] is True:
        f_by = format_count(status["followers"])
        f_to = format_count(status["following"])
        caption = (
            f"ℹ️ <b>{ig_link}</b> is already active.\n\n"
            f"Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
            f"👤 Requested by: {user_mention}"
        )
        sent = send_custom_media(message.chat.id, "deny", caption, reply_to=message.message_id)
        if sent:
            auto_delete_after_delay(message.chat.id, sent.message_id, delay_seconds=300)
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
    db.setdefault("stats", {})["total_monitored"] = db.get("stats", {}).get("total_monitored", 0) + 1
    if str(user_id) in db.get("users", {}):
        db["users"][str(user_id)]["req_count"] = db["users"][str(user_id)].get("req_count", 0) + 1
    save_db(db)

    caption = (
        "🔍 <b>Instagram Account Monitoring Added</b>\n\n"
        f"Target: <b>{ig_link}</b>\n"
        "You'll be notified as soon as the account is active.\n\n"
        f"👤 Requested by: {user_mention}"
    )

    send_custom_media(message.chat.id, "ub_req", caption, reply_to=message.message_id)

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

    ig_link = get_ig_link(username)

    if username in db.get("ban_monitors", {}):
        bot.reply_to(message, f"⚠️ <b>{ig_link}</b> is already being monitored.")
        return

    status = get_instagram_details(username)
    if status["active"] is False:
        caption = (
            f"ℹ️ <b>{ig_link}</b> is already banned or unavailable.\n\n"
            f"👤 Requested by: {user_mention}"
        )
        sent = send_custom_media(message.chat.id, "deny", caption, reply_to=message.message_id)
        if sent:
            auto_delete_after_delay(message.chat.id, sent.message_id, delay_seconds=300)
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
    db.setdefault("stats", {})["total_monitored"] = db.get("stats", {}).get("total_monitored", 0) + 1
    if str(user_id) in db.get("users", {}):
        db["users"][str(user_id)]["req_count"] = db["users"][str(user_id)].get("req_count", 0) + 1
    save_db(db)

    caption = (
        "🔍 <b>Instagram Account Monitoring Added</b>\n\n"
        f"Target: <b>{ig_link}</b>\n"
        f"Current Followers: <code>{f_by}</code> | Following: <code>{f_to}</code>\n"
        "You'll be notified as soon as the account is banned.\n\n"
        f"👤 Requested by: {user_mention}"
    )

    send_custom_media(message.chat.id, "b_req", caption, reply_to=message.message_id)

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
            ig_link = get_ig_link(u)
            lines.append(f"• <b>{ig_link}</b> (Elapsed: <code>{t}</code>) — {mention}")

    if bans:
        lines.append("\n<b>Awaiting Ban (/b):</b>")
        for u, d in bans.items():
            t = format_time_taken(time.time() - d["start_time"])
            f_by = format_count(d.get("followers", "N/A"))
            mention = get_user_mention(d.get("user_id"), d.get("user_name"))
            ig_link = get_ig_link(u)
            lines.append(f"• <b>{ig_link}</b> (Followers: <code>{f_by}</code> | Elapsed: <code>{t}</code>) — {mention}")

    bot.reply_to(message, "\n".join(lines))

@bot.message_handler(func=lambda msg: True, content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker', 'animation'])
def handle_unrecognized_input(message):
    user = message.from_user
    register_user(user, message.chat.id)
    track_and_clean_spam(message.chat.id, user.id, message.message_id)

    if message.chat.type != "private":
        return

    missing = get_missing_channels(user.id)
    if missing and not is_admin_or_owner(user.id):
        mention = get_user_mention(user.id, user.first_name)
        text = (
            "⚠️ <b>Access Restricted</b>\n\n"
            f"Hello {mention}, you must join all our required official channels below to access this bot:\n\n"
            "<i>Click each channel to join, then tap Verify:</i>"
        )
        send_custom_media(message.chat.id, "force_join", text, reply_to=message.message_id, reply_markup=build_force_join_markup())
        return

    mention = get_user_mention(user.id, user.first_name)
    sub_text = (
        "<b>Instagram Monitor Bot 24x7</b>\n"
        "<b>Want Subscription?</b>\n\n"
        f"Hey {mention},\n"
        f"Send your ID (<code>{user.id}</code>) to owner to claim your Paid subscription."
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Contact Owner", url="https://t.me/talkwithhimbot"),
        types.InlineKeyboardButton("Join Main Channel", url="https://t.me/+ObinPrPz_ktkODJl")
    )

    sent = send_custom_media(message.chat.id, "subscription", sub_text, reply_to=message.message_id, reply_markup=markup)
    if sent:
        auto_delete_after_delay(message.chat.id, sent.message_id, delay_seconds=300)

def run_bot_polling():
    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)
            print("Starting TeleBot Polling...", flush=True)
            bot.infinity_polling(timeout=20, long_polling_timeout=15, skip_pending=True, none_stop=True)
        except Exception as e:
            print(f"[RECONNECT] {e}. Reconnecting in 3s...", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    _verify_integrity()
    print("Dual Tracker Bot is active and running...", flush=True)
    run_bot_polling()
