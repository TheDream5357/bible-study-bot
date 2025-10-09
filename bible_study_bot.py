# bible_study_bot.py

import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz

# ===============================
# CONFIGURATION
# ===============================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID"))

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday"]
MAX_SIGNUPS_PER_DAY = 2

# In-memory signups
signups = {day: [] for day in DAYS}

# ===============================
# LOGGING
# ===============================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===============================
# HANDLERS
# ===============================

def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Bible Study Bot active! Use /signup to sign up for a day.")

def signup(update: Update, context: CallbackContext):
    keyboard = []
    for day in DAYS:
        slots_left = MAX_SIGNUPS_PER_DAY - len(signups[day])
        label = f"{day} ({slots_left} slots left)"
        keyboard.append([InlineKeyboardButton(label, callback_data=day)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select a day to sign up:", reply_markup=reply_markup)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user.username or query.from_user.first_name
    day = query.data

    if user in signups[day]:
        signups[day].remove(user)
        query.answer(text=f"You cancelled your signup for {day}.")
    elif len(signups[day]) < MAX_SIGNUPS_PER_DAY:
        signups[day].append(user)
        query.answer(text=f"You signed up for {day}!")
    else:
        query.answer(text=f"{day} is full!")

    query.edit_message_text(text="Updated signups:")
    for d in DAYS:
        query.message.reply_text(f"{d}: {', '.join(signups[d]) or 'No signups yet'}")

# ===============================
# SCHEDULED MESSAGES
# ===============================

def send_signup_message(context: CallbackContext):
    context.bot.send_message(chat_id=GROUP_CHAT_ID, text="📋 Weekly Bible Study signups are open! Use /signup to pick your day.")

def send_reminder(context: CallbackContext):
    # Check for unfilled slots
    unfilled = [day for day in DAYS if len(signups[day]) < MAX_SIGNUPS_PER_DAY]
    if unfilled:
        text = "⏰ Reminder! Some Bible Study slots are still available:\n"
        for day in unfilled:
            slots_left = MAX_SIGNUPS_PER_DAY - len(signups[day])
            text += f"{day}: {slots_left} slot(s) left\n"
        context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text)

def send_final_schedule(context: CallbackContext):
    text = "📅 Final Bible Study Schedule for the week:\n"
    for day in DAYS:
        text += f"{day}: {', '.join(signups[day]) or 'No signups yet'}\n"
    context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text)

# ===============================
# MAIN FUNCTION
# ===============================

def main():
    logger.info("Starting Bible Study Bot...")
    
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("signup", signup))
    dp.add_handler(CallbackQueryHandler(button))

    # Start the bot
    updater.start_polling()

    # Scheduler
    scheduler = BackgroundScheduler(timezone=pytz.timezone("US/Eastern"))
    scheduler.add_job(send_signup_message, "cron", day_of_week="fri", hour=9, minute=0, args=[updater.job_queue])
    scheduler.add_job(send_reminder, "cron", day_of_week="sun", hour=12, minute=0, args=[updater.job_queue])
    scheduler.add_job(send_final_schedule, "cron", day_of_week="sun", hour=21, minute=0, args=[updater.job_queue])
    scheduler.start()

    logger.info("Bot started and polling Telegram...")
    updater.idle()

if __name__ == "__main__":
    main()
