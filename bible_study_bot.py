import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
)
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from datetime import datetime

# ========================
# Setup and Configuration
# ========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get from Render environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("GROUP_CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or GROUP_CHAT_ID in environment variables.")

# Store signups (in memory)
signups = {
    "Monday": [],
    "Tuesday": [],
    "Wednesday": [],
    "Thursday": []
}

# ========================
# Helper Functions
# ========================
def build_keyboard():
    keyboard = []
    for day in signups:
        button_text = f"{day} ({len(signups[day])} signed up)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=day)])
    return InlineKeyboardMarkup(keyboard)

def get_schedule_text():
    message = "📅 *Bible Study Schedule for the Week:*\n\n"
    for day, people in signups.items():
        if people:
            message += f"✅ *{day}:* {', '.join(people)}\n"
        else:
            message += f"🕓 *{day}:* No one signed up yet\n"
    return message

def reset_signups():
    for day in signups:
        signups[day] = []

# ========================
# Telegram Bot Handlers
# ========================
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Welcome to the Bible Study Sign-up Bot! 🙏\n\n"
        "Use /signup to pick a day to lead.\n"
        "You can also /cancel your signup or view the /schedule."
    )

def signup(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Please select the day you'd like to sign up for:",
        reply_markup=build_keyboard()
    )

def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user.first_name
    day = query.data
    query.answer()

    if user in signups[day]:
        signups[day].remove(user)
        response = f"{user} canceled their signup for {day}."
    else:
        signups[day].append(user)
        response = f"{user} signed up for {day}."

    query.edit_message_text(text=get_schedule_text(), parse_mode="Markdown")
    logger.info(response)

def cancel(update: Update, context: CallbackContext):
    user = update.message.from_user.first_name
    removed = False
    for day, users in signups.items():
        if user in users:
            users.remove(user)
            removed = True
    if removed:
        update.message.reply_text("Your signup has been canceled.")
    else:
        update.message.reply_text("You have no active signups.")

def schedule(update: Update, context: CallbackContext):
    update.message.reply_text(get_schedule_text(), parse_mode="Markdown")

# ========================
# Scheduler Tasks
# ========================
def send_signup_message():
    """Send signup message every Friday morning."""
    logger.info("Sending Friday signup message...")
    context = updater.bot
    context.send_message(
        chat_id=CHAT_ID,
        text="📖 *Bible Study Sign-up Time!*\n\nPlease pick a day to teach next week:",
        reply_markup=build_keyboard(),
        parse_mode="Markdown"
    )

def send_reminder_message():
    """Send Sunday reminder if slots aren’t filled."""
    logger.info("Sending Sunday reminder message...")
    unfilled = [day for day, users in signups.items() if not users]
    if unfilled:
        message = (
            "⚠️ *Reminder:* Some days are still open!\n\n"
            + ", ".join(unfilled)
            + "\nPlease sign up if you can 🙏"
        )
        updater.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")

def send_final_schedule():
    """Send final schedule Sunday night."""
    logger.info("Sending final schedule...")
    updater.bot.send_message(chat_id=CHAT_ID, text=get_schedule_text(), parse_mode="Markdown")

# ========================
# Main Function
# ========================
def main():
    global updater
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("signup", signup))
    dp.add_handler(CallbackQueryHandler(button_click))
    dp.add_handler(CommandHandler("cancel", cancel))
    dp.add_handler(CommandHandler("schedule", schedule))

    # Scheduler setup
    scheduler = BackgroundScheduler(timezone=pytz.timezone("US/Eastern"))
    scheduler.add_job(send_signup_message, "cron", day_of_week="fri", hour=9, minute=0)
    scheduler.add_job(send_reminder_message, "cron", day_of_week="sun", hour=12, minute=0)
    scheduler.add_job(send_final_schedule, "cron", day_of_week="sun", hour=21, minute=0)
    scheduler.start()

    logger.info("Bible Study Bot started successfully.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
