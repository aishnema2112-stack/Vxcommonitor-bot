import os
import sys
import time
import json
import re
import threading
import io
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

CHECK_INTERVAL_SECONDS = 15
DB_FILE = "dual_tracker_db.json"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", disable_web_page_preview=True)

# In-memory transient state for admin flows
admin_state = {}

# ----------------- DATABASE -----------------
def load_db():
    default_data = {
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
            {"id": "c1", "name": "📢 Jyoex", "tag": "@jyoex", "link": "https://t.me/jyoex", "color": "🟢"},
            {"id": "c2", "name": "📢 Comchater", "tag": "@Comchater", "link": "https://t.me/Comchater", "color": "🟢"},
            {"id": "c3", "name": "📢 Foraremy", "tag": "@Foraremy", "link": "https://t.me/Foraremy", "color": "🟢"}
        ],
        "media": {
            "ub_req": {"type": "animation", "id": "https://media.giphy.com/media/3o7TKTDnUxE0g2fSE8/giphy.gif"},
            "ub_done": {"type": "animation", "id": "https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif"},
            "b_req": {"type": "animation", "id": "https://media.giphy.com/media/3o7TKTDnUxE0g2fSE8/giphy.gif"},
            "b_done": {"type": "animation", "id": "https://media.giphy.com/media/l2YWg3f6m0tI7Ff2w/giphy.gif"},
            "deny": {"type": "animation", "id": "https://media.giphy.com/media/13d2jHlSlxklVe/giphy.gif"}
        }
    }
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

def get_full_timestamp():
    return datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")

def get_user_mention(user_id, first_name):
    clean_name = first_name.replace("<", "").replace(">", "") if first_name else "User"
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'

def get_ig_link(username):
    clean_user = username.strip().replace("@", "")
    return f'<a href="https://instagram.com/{clean_user}">@{clean_user}</a>'

def is_admin_or_owner(user_id, username=None):
    if user_id in db.get("admins", []):
        return True
    if username and username.lower().replace("@", "") in ["jyoex", "shivuu_vxcom", "shivuu"]:
        if user_id not in db["admins"]:
            db["admins"].append(user_id)
            save_db(db)
        return True
    return False

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
                    bot.send_message(adm, alert_text)
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
        print(f"Media send fallback: {e}")
        return bot.send_message(chat_id=chat_id, text=caption, reply_to_message_id=reply_to)

# ----------------- FORCE JOIN VERIFICATION -----------------
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
        btn_label = f"{ch.get('color', '🟢')} {ch['name']}"
        markup.add(types.InlineKeyboardButton(btn_label, url=ch["link"]))
    markup.add(types.InlineKeyboardButton("✅ Verify / Try Again", callback_data="verify_channels"))
    return markup

def check_access(message):
    user = message.from_user
    chat = message.chat
    register_user(user, chat.id)

    if is_admin_or_owner(user.id, user.username):
        return True

    if db.get("settings", {}).get("maintenance", False):
        maintenance_msg = (
            "🛠 <b>System Maintenance Notice</b>\n\n"
            "Our servers are currently undergoing scheduled upgrades and optimization.\n"
            "All monitoring requests are temporarily paused.\n\n"
            "<i>We will be back online shortly. Thank you for your patience!</i>"
        )
        bot.reply_to(message, maintenance_msg)
        return False

    missing = get_missing_channels(user.id)
    if missing:
        mention = get_user_mention(user.id, user.first_name)
        channel_bullets = "\n".join([f"• {c['tag']}" for c in db.get("channels", [])])
        text = (
            f"⚠️ <b>Access Restricted</b>\n\n"
            f"Hello {mention}, you must join all our official channels before using this bot:\n\n"
            f"{channel_bullets}\n\n"
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
            print(f"Loop error: {e}")
            time.sleep(10)

threading.Thread(target=monitor_loop, daemon=True).start()

# ----------------- ADMIN DASHBOARD -----------------
def get_admin_panel_markup():
    m_status = "🟢 ON" if db.get("settings", {}).get("maintenance", False) else "⚪ OFF"
    n_status = "🔔 ON" if db.get("settings", {}).get("new_user_notify", True) else "🔕 OFF"

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📬 Mailing", callback_data="admin_mailing"),
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
    if user_id not in db["admins"]:
        db["admins"].append(user_id)
        save_db(db)
    bot.reply_to(message, "👑 <b>Success:</b> You are now registered as Owner/Admin! Send <code>/admin</code> to open panel.")

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    user_id = message.from_user.id
    if not is_admin_or_owner(user_id, message.from_user.username):
        bot.reply_to(message, "<b>Access Denied:</b> Send <code>/claim</code> in private DM first.")
        return
    
    admin_text = (
        "🔧 <b>Administrator Control Panel</b>\n\n"
        "Welcome to the bot master management dashboard.\n"
        "Select an action from the options below:"
    )
    bot.reply_to(message, admin_text, reply_markup=get_admin_panel_markup())

# ----------------- CALLBACK HANDLERS FOR ADMIN -----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_") or call.data.startswith("toggle_") or call.data.startswith("set_") or call.data.startswith("btn_") or call.data.startswith("view_"))
def handle_admin_callbacks(call):
    user_id = call.from_user.id
    if not is_admin_or_owner(user_id, call.from_user.username):
        bot.answer_callback_query(call.id, "Access Denied", show_alert=True)
        return

    data = call.data

    if data == "admin_close":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    # 1. Mailing
    if data == "admin_mailing":
        admin_state[user_id] = "waiting_broadcast"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_action"))
        bot.edit_message_text(
            "📬 <b>Mailing / Broadcast Mode</b>\n\n"
            "Please send or <b>FORWARD</b> the message you want to broadcast.\n"
            "You can forward from any channel or send Text, Photo, Video, GIF, or Documents.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    # 2. Statistics
    if data == "admin_stats":
        total_users = len(db.get("users", {}))
        total_groups = len(db.get("groups", []))
        ub_count = len(db.get("unban_monitors", {}))
        b_count = len(db.get("ban_monitors", {}))
        total_tracked = db.get("stats", {}).get("total_monitored", 0) + ub_count + b_count

        stats_text = (
            "📊 <b>Bot Real-time Analytics Dashboard</b>\n\n"
            f"👤 <b>Total Unique Users:</b> <code>{total_users:,}</code>\n"
            f"👥 <b>Active Registered Groups:</b> <code>{total_groups}</code>\n"
            f"⚡ <b>Awaiting Unban (/ub):</b> <code>{ub_count}</code>\n"
            f"🚫 <b>Awaiting Ban (/b):</b> <code>{b_count}</code>\n"
            f"📈 <b>Total Accounts Tracked:</b> <code>{total_tracked:,}</code>\n"
            f"🕒 <b>Server Status:</b> <code>Online 24/7 (Render)</code>"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📑 View All Users List", callback_data="admin_user_list"),
            types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back")
        )
        bot.edit_message_text(stats_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
        return

    # 2.1 View All Users List
    if data == "admin_user_list":
        users = db.get("users", {})
        if not users:
            bot.answer_callback_query(call.id, "No users registered yet.", show_alert=True)
            return

        if len(users) <= 15:
            lines = ["📋 <b>Registered Users List:</b>\n"]
            for uid, u in users.items():
                m = get_user_mention(u.get("id", uid), u.get("name", "User"))
                lines.append(f"• {m} | <code>{uid}</code> | {u.get('username')} | Req: <code>{u.get('req_count', 0)}</code>")
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_stats"))
            bot.edit_message_text("\n".join(lines), chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
        else:
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

    # 3. Toggle Maintenance
    if data == "toggle_maintenance":
        curr = db.setdefault("settings", {}).get("maintenance", False)
        db["settings"]["maintenance"] = not curr
        save_db(db)
        state_str = "ENABLED (ON)" if not curr else "DISABLED (OFF)"
        bot.answer_callback_query(call.id, f"Maintenance Mode {state_str}", show_alert=True)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_panel_markup())
        return

    # 4. Toggle New User Notify
    if data == "toggle_notify":
        curr = db.setdefault("settings", {}).get("new_user_notify", True)
        db["settings"]["new_user_notify"] = not curr
        save_db(db)
        state_str = "ENABLED (ON)" if not curr else "DISABLED (OFF)"
        bot.answer_callback_query(call.id, f"New User Alert {state_str}", show_alert=True)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_admin_panel_markup())
        return

    # 5. Media Customizer Sub-Menu
    if data == "admin_media":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("1️⃣ /ub Request Alert GIF/Media", callback_data="set_ub_req"),
            types.InlineKeyboardButton("2️⃣ /ub Recovered Alert GIF/Media", callback_data="set_ub_done"),
            types.InlineKeyboardButton("3️⃣ /b Request Alert GIF/Media", callback_data="set_b_req"),
            types.InlineKeyboardButton("4️⃣ /b Banned Success Alert GIF/Media", callback_data="set_b_done"),
            types.InlineKeyboardButton("5️⃣ ⚠️ Deny Alert GIF/Media", callback_data="set_deny"),
            types.InlineKeyboardButton("👁 View All Set Media", callback_data="view_all_media"),
            types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back")
        )
        bot.edit_message_text(
            "🖼 <b>Manage & Customize Media:</b>\n\n"
            "Select any alert stage below to update its Photo/GIF/Video, or tap View to check current media:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    # 5.1 Set Media
    if data.startswith("set_"):
        action = data.replace("set_", "")
        admin_state[user_id] = f"waiting_media_{action}"
        names = {
            "ub_req": "/ub Request Added Alert",
            "ub_done": "/ub Recovered Alert",
            "b_req": "/b Request Added Alert",
            "b_done": "/b Banned Success Alert",
            "deny": "Deny / Active Alert"
        }
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_action"))
        bot.edit_message_text(
            f"📸 <b>Send Media for {names.get(action, action)}</b>\n\n"
            "Please send or forward the <b>Photo, GIF, or Video</b> right now in this chat.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    # 5.2 View All Media
    if data == "view_all_media":
        bot.answer_callback_query(call.id, "Sending all previews...")
        stages = [
            ("ub_req", "1. /ub Request Alert"),
            ("ub_done", "2. /ub Recovered Alert"),
            ("b_req", "3. /b Request Alert"),
            ("b_done", "4. /b Banned Alert"),
            ("deny", "5. Deny Alert")
        ]
        for key, name in stages:
            send_custom_media(call.message.chat.id, key, f"Current Media for: <b>{name}</b>")
            time.sleep(0.4)
        return

    # 6. Button Customizer Menu
    if data == "admin_btn_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in db.get("channels", []):
            markup.add(
                types.InlineKeyboardButton(f"✏️ Rename: {ch['name']}", callback_data=f"btn_name_{ch['id']}"),
                types.InlineKeyboardButton(f"🎨 Color Theme: {ch.get('color', '🟢')}", callback_data=f"btn_color_{ch['id']}")
            )
        markup.add(types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        bot.edit_message_text(
            "🔘 <b>Force Join Button Customizer</b>\n\n"
            "Change Button text or color emojis for your channels:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    # 6.1 Change Button Name
    if data.startswith("btn_name_"):
        cid = data.replace("btn_name_", "")
        admin_state[user_id] = f"waiting_btn_name_{cid}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="cancel_action"))
        bot.edit_message_text(
            f"✏️ <b>Enter New Button Text for Channel ({cid}):</b>\n\n"
            "Type and send the new name (e.g., <i>📢 Official Network</i>):",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    # 6.2 Change Button Color Theme
    if data.startswith("btn_color_"):
        cid = data.replace("btn_color_", "")
        markup = types.InlineKeyboardMarkup(row_width=3)
        colors = ["🟢", "🔴", "🔵", "🟡", "🟣", "⚫", "⚪", "🔥", "⚡"]
        buttons = [types.InlineKeyboardButton(c, callback_data=f"setcol_{cid}_{c}") for c in colors]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_btn_menu"))
        bot.edit_message_text(
            f"🎨 <b>Select Color Emoji for Channel ({cid}):</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    # 6.3 Set Color Callback
    if data.startswith("setcol_"):
        parts = data.split("_")
        cid = parts[1]
        color = parts[2]
        for ch in db.get("channels", []):
            if ch["id"] == cid:
                ch["color"] = color
                break
        save_db(db)
        bot.answer_callback_query(call.id, f"Color updated to {color}", show_alert=True)
        # Refresh button menu
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in db.get("channels", []):
            markup.add(
                types.InlineKeyboardButton(f"✏️ Rename: {ch['name']}", callback_data=f"btn_name_{ch['id']}"),
                types.InlineKeyboardButton(f"🎨 Color Theme: {ch.get('color', '🟢')}", callback_data=f"btn_color_{ch['id']}")
            )
        markup.add(types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_back"))
        bot.edit_message_text("🔘 <b>Force Join Button Customizer</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
        return

    # 7. Manage Admins
    if data == "admin_manage":
        adms = db.get("admins", [])
        adm_lines = [f"• <code>{a}</code>" for a in adms]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_back"))
        bot.edit_message_text(
            "👥 <b>Authorized Admins:</b>\n\n" + "\n".join(adm_lines),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
        return

    # Back
    if data == "admin_back":
        bot.edit_message_text(
            "🔧 <b>Administrator Control Panel</b>\n\nSelect an action below:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_admin_panel_markup()
        )
        return

@bot.callback_query_handler(func=lambda call: call.data == "cancel_action")
def handle_cancel_action(call):
    admin_state.pop(call.from_user.id, None)
    bot.answer_callback_query(call.id, "Action cancelled.")
    bot.edit_message_text(
        "🔧 <b>Administrator Control Panel</b>\n\nSelect an action below:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=get_admin_panel_markup()
    )

# ----------------- ADMIN INPUT LISTENERS (MAILING, MEDIA, BUTTONS) -----------------
@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'document', 'audio', 'voice', 'sticker'], func=lambda msg: msg.from_user.id in admin_state)
def process_admin_inputs(message):
    user_id = message.from_user.id
    state = admin_state.get(user_id)

    if message.text and message.text.lower() in ["/cancel", "cancel"]:
        admin_state.pop(user_id, None)
        bot.reply_to(message, "❌ <b>Action Cancelled.</b>", reply_markup=get_admin_panel_markup())
        return

    # A. Mailing Broadcast
    if state == "waiting_broadcast":
        admin_state.pop(user_id, None)
        status_msg = bot.reply_to(message, "⏳ <b>Broadcasting message to all users and groups...</b>")

        targets = list(db.get("users", {}).keys()) + db.get("groups", [])
        total = len(targets)
        sent = 0
        failed = 0

        for target in targets:
            try:
                bot.copy_message(chat_id=target, from_chat_id=message.chat.id, message_id=message.message_id)
                sent += 1
                time.sleep(0.04)
            except Exception:
                failed += 1

        report = (
            "✅ <b>Mailing Broadcast Completed!</b>\n\n"
            f"• <b>Total Targets:</b> <code>{total}</code>\n"
            f"• <b>Delivered Successfully:</b> <code>{sent}</code>\n"
            f"• <b>Failed / Blocked:</b> <code>{failed}</code>"
        )
        bot.edit_message_text(report, chat_id=message.chat.id, message_id=status_msg.message_id)
        return

    # B. Set Button Name
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

    # C. Set Media
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
            bot.reply_to(message, "❌ Invalid media type. Please send a Photo, GIF, or Video.")

# ----------------- REGULAR USER COMMANDS -----------------
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
