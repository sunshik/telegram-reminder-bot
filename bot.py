import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from datetime import datetime
import sqlite3
import re


# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('reminders.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS reminders
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       chat_id INTEGER,
                       reminder_text TEXT,
                       reminder_date TEXT)''')
    conn.commit()
    conn.close()


def add_reminder(chat_id, text, date):
    print(f"📌 Добавляем в БД: {chat_id=} {text=} {date=}")
    conn = sqlite3.connect('reminders.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reminders (chat_id, reminder_text, reminder_date) VALUES (?, ?, ?)",
                   (chat_id, text, date))
    conn.commit()
    conn.close()


def check_reminders(context: CallbackContext):
    conn = sqlite3.connect('reminders.db')
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("SELECT id, chat_id, reminder_text FROM reminders WHERE reminder_date <= ?", (now,))
    reminders = cursor.fetchall()
    for reminder in reminders:
        try:
            context.bot.send_message(chat_id=reminder[1], text=f"⏰ Напоминание: {reminder[2]}")
            cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder[0],))
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
    conn.commit()
    conn.close()


def start(update: Update, context: CallbackContext):
    print("📩 /start получена!")
    update.message.reply_text('Привет! Я бот-напоминалка...')

def handle_message(update: Update, context: CallbackContext):
    try:
        text = update.message.text
        chat_id = update.message.chat.id

        print(f"💬 ПОЛУЧЕНО СООБЩЕНИЕ: {text}")

        match = re.match(r'(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}) (.+)', text)
        if match:
            date_str, reminder_text = match.groups()
            try:

                reminder_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M").strftime("%Y-%m-%d %H:%M")
                print(f"📆 Дата распознана как: {reminder_date}")
                add_reminder(chat_id, reminder_text, reminder_date)

                update.message.reply_text(f"✅ Напоминание создано на {date_str}!")
            except ValueError:
                update.message.reply_text("❌ Неверный формат даты! Используй ДД.ММ.ГГГГ ЧЧ:ММ")
        else:
            update.message.reply_text("❌ Неверный формат! Пример:\n\n'15.08.2025 14:00 Поздравить друга'")

    except Exception as e:
        print("❌ ОШИБКА В handle_message:", e)
        update.message.reply_text("🚨 Произошла ошибка при обработке.")

def main():
    init_db()

    import os
    TOKEN = os.environ.get("BOT_TOKEN")
    updater = Updater(TOKEN, use_context=True)
    
    updater.bot.delete_webhook()  # 💥 Обязательно, если раньше был Webhook

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    job_queue = updater.job_queue
    job_queue.run_repeating(check_reminders, interval=60, first=0)

    updater.start_polling()
    updater.idle()



if __name__ == '__main__':
    main()


