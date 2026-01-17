import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials


# ================== НАСТРОЙКИ ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")

if not all([BOT_TOKEN, GOOGLE_CREDENTIALS_JSON, SPREADSHEET_ID, SHEET_NAME]):
    raise RuntimeError("Не заданы все ENV переменные (используются старые имена)")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# ================== GOOGLE SHEETS ==================

def get_worksheet():
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_JSON,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)
    return worksheet


def append_to_sheet(row: list):
    ws = get_worksheet()
    ws.append_row(row, value_input_option="USER_ENTERED")


# ================== BOT LOGIC ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Привет.\n"
        "Опиши новый камень одним сообщением.\n\n"
        "Формат свободный:\n"
        "название, тип, цвет, вес, происхождение, примечания.\n\n"
        "Когда отправишь — данные будут сохранены в таблицу."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text:
        await update.message.reply_text("Пусто. Напиши описание камня.")
        return

    # простая структура: всё в одну ячейку + дата + user id
    row = [
        text,
        str(update.effective_user.id),
        update.message.date.isoformat(),
    ]

    try:
        append_to_sheet(row)
    except Exception as e:
        logger.exception("Ошибка записи в таблицу")
        await update.message.reply_text("Ошибка записи в таблицу. Проверь доступы.")
        return

    context.user_data.clear()

    await update.message.reply_text(
        "Готово. Камень добавлен в таблицу.\n"
        "Можешь вводить следующий."
    )


# ================== ENTRY POINT ==================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
