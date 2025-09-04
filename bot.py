import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from datetime import datetime, timedelta
import sqlite3
import re
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_PATH = 'reminders.db'

# ---------- База данных ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS reminders
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       chat_id INTEGER,
                       reminder_text TEXT,
                       reminder_date TEXT)''')
    conn.commit()
    conn.close()

def add_reminder(chat_id, text, date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reminders (chat_id, reminder_text, reminder_date) VALUES (?, ?, ?)",
                   (chat_id, text, date))
    conn.commit()
    conn.close()

def get_reminders(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, reminder_text, reminder_date FROM reminders WHERE chat_id = ? ORDER BY reminder_date", (chat_id,))
    reminders = cursor.fetchall()
    conn.close()
    return reminders

def delete_reminder(reminder_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

def update_reminder(reminder_id, new_text=None, new_date=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if new_text and new_date:
        cursor.execute("UPDATE reminders SET reminder_text = ?, reminder_date = ? WHERE id = ?", (new_text, new_date, reminder_id))
    elif new_text:
        cursor.execute("UPDATE reminders SET reminder_text = ? WHERE id = ?", (new_text, reminder_id))
    elif new_date:
        cursor.execute("UPDATE reminders SET reminder_date = ? WHERE id = ?", (new_date, reminder_id))
    conn.commit()
    conn.close()

# ---------- Проверка напоминаний ----------
def check_reminders(context: CallbackContext):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
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

# ---------- Команды ----------
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привет! Я бот-напоминалка.\n\n"
        "Добавляй напоминания в формате:\n"
        "ДД.MM.ГГГГ ЧЧ:ММ текст\n\n"
        "Основные команды:\n"
        "/list - показать все напоминания\n"
        "/delete - удалить напоминание\n"
        "/edit - изменить напоминание\n"
        "/snooze - отложить ближайшее\n"
        "/clear - удалить все\n"
        "/stats - статистика\n"
        "/help - подробная помощь"
    )

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Форматы команд:\n\n"
        "/list - список всех напоминаний\n"
        "/delete <номер> - удалить напоминание\n"
        "/edit <номер> <ДД.MM.ГГГГ ЧЧ:ММ текст> - редактировать напоминание\n"
        "/snooze <10m/1h/1d> - отложить ближайшее напоминание\n"
        "/clear - удалить все напоминания\n"
        "/stats - статистика"
    )

def handle_message(update: Update, context: CallbackContext):
    try:
        text = update.message.text
        chat_id = update.message.chat.id

        match = re.match(r'(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}) (.+)', text)
        if match:
            date_str, reminder_text = match.groups()
            reminder_date_local = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            # Перевод в UTC (например для +3)
            reminder_date_utc = reminder_date_local - timedelta(hours=3)
            reminder_date = reminder_date_utc.strftime("%Y-%m-%d %H:%M")
            add_reminder(chat_id, reminder_text, reminder_date)
            update.message.reply_text(f"✅ Напоминание создано на {date_str}!")
        else:
            update.message.reply_text("❌ Неверный формат! Пример:\n'15.08.2025 14:00 Позвонить другу'")
    except Exception as e:
        logger.error(f"Ошибка handle_message: {e}")
        update.message.reply_text("🚨 Произошла ошибка при обработке.")

def list_reminders(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    reminders = get_reminders(chat_id)
    if not reminders:
        update.message.reply_text("Список напоминаний пуст.")
        return
    msg = "\n".join([f"{i+1}. {r[2]} - {r[1]}" for i, r in enumerate(reminders)])
    update.message.reply_text(msg)

def delete_command(update: Update, context: CallbackContext):
    try:
        idx = int(context.args[0]) - 1
        chat_id = update.message.chat.id
        reminders = get_reminders(chat_id)
        if idx < 0 or idx >= len(reminders):
            update.message.reply_text("❌ Неверный номер напоминания.")
            return
        delete_reminder(reminders[idx][0])
        update.message.reply_text("✅ Напоминание удалено.")
    except (IndexError, ValueError):
        update.message.reply_text("Использование: /delete <номер>")

# ---------- Основная функция ----------
def main():
    init_db()
    TOKEN = os.environ.get("BOT_TOKEN")
    updater = Updater(TOKEN, use_context=True)

    updater.bot.delete_webhook()

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("list", list_reminders))
    dp.add_handler(CommandHandler("delete", delete_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    job_queue = updater.job_queue
    job_queue.run_repeating(check_reminders, interval=60, first=0)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
    
