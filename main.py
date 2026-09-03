import os
import time
import threading
import requests
import telebot
import psycopg2
from flask import Flask

# Flask app for Render health check
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Server is active and healthy!", 200

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "instagram-scraper-stable-api.p.rapidapi.com"

bot = telebot.TeleBot(BOT_TOKEN)

# Database Connection Initialization
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitored_accounts (
            username TEXT PRIMARY KEY,
            status TEXT,
            followers TEXT,
            following TEXT,
            requested_by TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()
    print("[DATABASE] Neon PostgreSQL Schema Verified & Initialized!", flush=True)

try:
    init_db()
except Exception as e:
    print(f"[DB INIT ERROR] {e}")

def log_user(message):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO bot_users (user_id, username, full_name) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING",
            (message.from_user.id, message.from_user.username or "N/A", message.from_user.first_name)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] Failed to log user: {e}", flush=True)

def check_single_account(username):
    username = username.strip().lower().replace("@", "")
    if not username:
        return {"status": "UNKNOWN", "followers": "N/A", "following": "N/A"}

    url = f"https://{RAPIDAPI_HOST}/get_ig_user_followers_v2.php"
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    }
    
    payload = {
        "username_or_url": f"https://www.instagram.com/{username}/",
        "data": "following",
        "amount": "1"
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        print(f"[RAPIDAPI] @{username} -> HTTP {response.status_code}", flush=True)

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                return {"status": "BANNED", "followers": 0, "following": 0}

            if data and not data.get("error") and data != []:
                followers_count = data.get("follower_count", "N/A")
                following_count = data.get("following_count", "N/A")
                return {
                    "status": "ACTIVE",
                    "followers": followers_count,
                    "following": following_count
                }

            return {"status": "BANNED", "followers": 0, "following": 0}

        elif response.status_code in (404, 403, 401):
            return {"status": "BANNED", "followers": 0, "following": 0}
        else:
            return {"status": "BANNED", "followers": 0, "following": 0}

    except Exception as e:
        print(f"[API ERROR] {e}", flush=True)
        return {"status": "UNKNOWN", "followers": "N/A", "following": "N/A"}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    log_user(message)
    bot.reply_to(message, "👋 Welcome to Instagram Monitor Bot!\nUse /b <username> to track an account.")

@bot.message_handler(commands=['b'])
def track_account(message):
    log_user(message)
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Usage: /b username\nExample: /b icxi4")
        return

    username = args[1].strip().lower().replace("@", "")
    user_name = message.from_user.first_name

    bot.reply_to(message, f"🔍 Checking status for @{username}...")
    result = check_single_account(username)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO monitored_accounts (username, status, followers, following, requested_by) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (username) DO UPDATE SET status = EXCLUDED.status",
            (username, result['status'], str(result['followers']), str(result['following']), user_name)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}", flush=True)

    bot.send_message(
        message.chat.id,
        f"🔍 **Instagram Account Monitoring Added**\n\nTarget: `@{username}`\nCurrent Status: **{result['status']}**\nFollowers: {result['followers']}\nFollowing: {result['following']}\nRequested by: {user_name}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['ub'])
def untrack_account(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Usage: /ub username")
        return

    username = args[1].strip().lower().replace("@", "")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM monitored_accounts WHERE username = %s", (username,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}", flush=True)

    bot.send_message(message.chat.id, f"🗑️ Stopped monitoring `@{username}`", parse_mode="Markdown")

def background_monitor():
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username, status FROM monitored_accounts")
            accounts = cursor.fetchall()
            cursor.close()
            conn.close()

            for username, old_status in accounts:
                result = check_single_account(username)
                new_status = result['status']

                if new_status != "UNKNOWN" and new_status != old_status:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE monitored_accounts SET status = %s WHERE username = %s", (new_status, username))
                    conn.commit()
                    cursor.close()
                    conn.close()

                    alert_text = f"🚨 **Instagram Account Banned!** Target `@{username}` is now banned." if new_status == "BANNED" else f"✅ **Instagram Account Active!** Target `@{username}` is back."
                    bot.send_message(chat_id=message_chat_id_fallback(), text=alert_text, parse_mode="Markdown")

        except Exception as e:
            print(f"[MONITOR ERROR] {e}", flush=True)

        time.sleep(60)

def message_chat_id_fallback():
    return os.getenv("DEFAULT_CHAT_ID", "@vxcommonitor")

if __name__ == "__main__":
    print("[INIT] Starting Bot with Full Background Monitor & Flask...", flush=True)
    threading.Thread(target=background_monitor, daemon=True).start()
    
    port = int(os.getenv("PORT", 10000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()
    
    bot.infinity_polling(skip_pending=True)
