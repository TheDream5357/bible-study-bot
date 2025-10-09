import pytz
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
)
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# ==============================
# 🔧 CONFIGURATION
# ==============================
TELEGRAM_BOT_TOKEN = "8299761756:AAEbkN3BpoUM0OAXuD_8RTWFeD58sKeDTs4"  # Replace with your BotFather token
GROUP_CHAT_ID = -4523749160  # Replace with your Telegram group ID
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday"]

# ==============================
# 📊 GLOBAL DATA STORAGE
# ==============================
signups = {day: [] for day in DAYS}  # e.g., {"Monday": ["Alex"], ...}
scheduler = BackgroundScheduler()

# ==============================
# 🪵 LOGGING
# ==============================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==============================
# 🧱 HELPER FUNCTIONS
# ==============================
def build_keyboard():
    """Create inline keyboard with signup buttons."""
    keyboard = []
    for day in DAYS:
        count = len(signups[day])
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{day} ({count} signed up)", callback_data=f"signup_{day}"
                )
            ]
        )
    keyboard.append([InlineKeyboardButton("Cancel my signup", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def format_schedule():
    """Format the weekly schedule as text."""
    msg = "📅 *Bible Study Schedule for This Week*\n(9:00–9:30 PM)\n\n"
    for day in DAYS:
        if signups[day]:
            names = ", ".join(signups[day])
            msg += f"• *{day}*: {names}\n"
        else:
            msg += f"• *{day}*: _No one yet_\n"
    return msg

# ==============================
# 📢 COMMAND HANDLERS
# ==============================
def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Bible Study Bot active! Use /signup to start signups.")

def signup(update: Update, context: CallbackContext):
    """Manually trigger signup message."""
    update.message.reply_text(
        "📖 Sign up for next week's Bible Study:", reply_markup=build_keyboard()
    )

def button(update: Update, context: CallbackContext):
    """Handle button clicks for signups and cancellations."""
    query = update.callback_query
    user = query.from_user.first_name
    data = query.data

    if data.startswith("signup_"):
        day = data.split("_")[1]
        # Allow multiple signups per day, prevent duplicate signup
        if user not in signups[day]:
            signups[day].append(user)
            query.answer(f"You signed up for {day}!")
        else:
            query.answer(f"You’re already signed up for {day}.")
    elif data == "cancel":
        removed = False
        for d in DAYS:
            if user in signups[d]:
                signups[d].remove(user)
                removed = True
        query.answer("Your signup was canceled." if removed else "You weren’t signed up.")

    query.edit_message_text(
        text="📖 Sign up for next week's Bible Study:", reply_markup=build_keyboard()
    )

def send_signup_message(context: CallbackContext):
    """Automatically send the signup message (every Friday)."""
    context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text="📖 Sign up for next week's Bible Study:",
        reply_markup=build_keyboard(),
    )

def send_reminder(context: CallbackContext):
    """Send reminder if not all slots filled (Sunday)."""
    unfilled = [day for day in DAYS if not signups[day]]
    if unfilled:
        msg = "⏰ Reminder: Some Bible Study days still need volunteers!\n\n"
        msg += "Unfilled days:\n" + "\n".join(f"• {d}" for d in unfilled)
        context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg)

def send_final_schedule(context: CallbackContext):
    """Send the final schedule (Sunday night)."""
    msg = format_schedule()
    context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg, parse_mode="Markdown")
    reset_schedule()

def reset_schedule():
    """Clear signups for a new week."""
    global signups
    signups = {day: [] for day in DAYS}
    logger.info("Schedule reset for new week.")

# ==============================
# 🚀 MAIN FUNCTION
# ==============================
def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("signup", signup))
    dp.add_handler(CallbackQueryHandler(button))

    # 🕒 Schedule automated messages
    scheduler.add_job(send_signup_message, "cron", day_of_week="fri", hour=9, minute=0, args=[updater.job_queue],timezone=pytz.timezone("US/Eastern"))
    scheduler.add_job(send_reminder, "cron", day_of_week="sun", hour=12, minute=0, args=[updater.job_queue],timezone=pytz.timezone("US/Eastern"))
    scheduler.add_job(send_final_schedule, "cron", day_of_week="sun", hour=21, minute=0, args=[updater.job_queue],timezone=pytz.timezone("US/Eastern"))
    scheduler.start()

    logger.info("Bible Study Bot started.")
    updater.start_polling()
    updater.idle()

# ==============================
# ▶️ RUN BOT
# ==============================
if __name__ == "__main__":
    main()
