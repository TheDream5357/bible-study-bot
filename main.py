import os
import logging
import sqlite3
import asyncio
from datetime import datetime
import pytz

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# -------------------- CONFIG --------------------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", 0))
TIMEZONE = os.environ.get("TIMEZONE", "America/New_York")

# -------------------- LOGGING --------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- DATABASE --------------------
def init_db():
    conn = sqlite3.connect("signups.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS signups (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            day TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_signup_table():
    conn = sqlite3.connect("signups.db")
    c = conn.cursor()
    c.execute("SELECT user_name, day FROM signups")
    rows = c.fetchall()
    conn.close()

    days = {"Monday": [], "Tuesday": [], "Wednesday": [], "Thursday": [], "Unavailable": []}
    for name, day in rows:
        if day in days:
            days[day].append(name)

    def fmt(names):
        return ", ".join(names) if names else "—"

    text = (
        "📅 *Bible Study Signups (Mon–Thu, 9–9:30 PM)*\n\n"
        f"📘 Monday: {fmt(days['Monday'])}\n"
        f"📗 Tuesday: {fmt(days['Tuesday'])}\n"
        f"📙 Wednesday: {fmt(days['Wednesday'])}\n"
        f"📕 Thursday: {fmt(days['Thursday'])}\n\n"
        f"❌ Not Available: {fmt(days['Unavailable'])}\n"
    )
    return text

# -------------------- SIGNUP MESSAGE --------------------
async def send_signup(context: ContextTypes.DEFAULT_TYPE, chat_id: int = None):
    if chat_id is None:
        chat_id = GROUP_CHAT_ID

    signup_text = get_signup_table()

    keyboard = [
        [
            InlineKeyboardButton("📘 Monday", callback_data="signup_Monday"),
            InlineKeyboardButton("📗 Tuesday", callback_data="signup_Tuesday"),
        ],
        [
            InlineKeyboardButton("📙 Wednesday", callback_data="signup_Wednesday"),
            InlineKeyboardButton("📕 Thursday", callback_data="signup_Thursday"),
        ],
        [InlineKeyboardButton("🚫 Not Available", callback_data="signup_Unavailable")],
        [
            InlineKeyboardButton("Change Day", callback_data="change_day"),
            InlineKeyboardButton("Cancel Signup", callback_data="cancel_signup")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=signup_text + "\nTap a day below to sign up or mark yourself unavailable 👇",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def manual_send_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_signup(context, update.effective_chat.id)

# -------------------- INLINE CALLBACKS --------------------
async def handle_signup_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    data = query.data
    await query.answer()

    conn = sqlite3.connect("signups.db")
    c = conn.cursor()

    if data.startswith("signup_"):
        day = data.split("_")[1]
        c.execute("INSERT OR REPLACE INTO signups (user_id, user_name, day) VALUES (?, ?, ?)",
                  (user_id, user_name, day))
        conn.commit()

    elif data == "cancel_signup":
        c.execute("DELETE FROM signups WHERE user_id=?", (user_id,))
        conn.commit()

    elif data == "change_day":
        keyboard = [
            [InlineKeyboardButton("📘 Monday", callback_data="change_Monday")],
            [InlineKeyboardButton("📗 Tuesday", callback_data="change_Tuesday")],
            [InlineKeyboardButton("📙 Wednesday", callback_data="change_Wednesday")],
            [InlineKeyboardButton("📕 Thursday", callback_data="change_Thursday")],
            [InlineKeyboardButton("🚫 Not Available", callback_data="change_Unavailable")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Which day would you like to switch to?", reply_markup=reply_markup)
        conn.close()
        return

    elif data.startswith("change_"):
        new_day = data.split("_")[1]
        c.execute("INSERT OR REPLACE INTO signups (user_id, user_name, day) VALUES (?, ?, ?)",
                  (user_id, user_name, new_day))
        conn.commit()

    conn.close()

    signup_text = get_signup_table()
    keyboard = [
        [
            InlineKeyboardButton("📘 Monday", callback_data="signup_Monday"),
            InlineKeyboardButton("📗 Tuesday", callback_data="signup_Tuesday"),
        ],
        [
            InlineKeyboardButton("📙 Wednesday", callback_data="signup_Wednesday"),
            InlineKeyboardButton("📕 Thursday", callback_data="signup_Thursday"),
        ],
        [InlineKeyboardButton("🚫 Not Available", callback_data="signup_Unavailable")],
        [
            InlineKeyboardButton("Change Day", callback_data="change_day"),
            InlineKeyboardButton("Cancel Signup", callback_data="cancel_signup")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        signup_text + "\nTap a day below to sign up or mark yourself unavailable 👇",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# -------------------- SCHEDULED SUNDAY MESSAGE --------------------
async def send_weekly_schedule(context: ContextTypes.DEFAULT_TYPE):
    signup_text = get_signup_table()
    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text="📖 *This Week’s Bible Study Schedule*\n\n" + signup_text + "\n🕘 Zoom: [link]",
        parse_mode="Markdown"
    )

# -------------------- COMMANDS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! Use /send_signup to post this week’s signup form."
    )

# -------------------- MAIN --------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send_signup", manual_send_signup))
    app.add_handler(CallbackQueryHandler(handle_signup_actions,
                                         pattern="^(signup_|change_|cancel_signup|change_day)"))

    scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
    scheduler.add_job(lambda: asyncio.create_task(send_signup(None)),
                      trigger="cron", day_of_week="fri", hour=12, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(send_weekly_schedule(None)),
                      trigger="cron", day_of_week="sun", hour=21, minute=0)
    scheduler.start()

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
