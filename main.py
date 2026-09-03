import os
import time
import threading
import requests
import telebot
import psycopg2
from flask import Flask

app = Flask(__name__)

@app.route('/')
def health_check():
    return "Server is active and healthy!", 200

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "instagram-scraper-stable-api.p.rapidapi.com"

bot = telebot.TeleBot(BOT_TOKEN)

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
    print("[DATABASE] Tables Initialized Successfully!", flush=True)

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
        print(f"[DB ERROR] Failed to log user: {e}")

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
        else:
            return {"status": "BANNED", "followers": 0, "following": 0}
    except Exception:
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
        print(f"[DB ERROR] {e}")

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
        print(f"[DB ERROR] {e}")

    bot.send_message(message.chat.id, f"🗑️ Stopped monitoring `@{username}`", parse_mode="Markdown")

if __name__ == "__main__":
    print("[INIT] Starting Bot with Flask and Polling...", flush=True)
    port = int(os.getenv("PORT", 10000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
