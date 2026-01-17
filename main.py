import logging
import os
import json

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
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


# ================== ЛОГИ ==================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ================== GOOGLE SHEETS ==================

def get_worksheet():
    creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)

    creds = Credentials.from_service_account_info(
        creds_info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)
    return sheet.worksheet(SHEET_NAME)


def append_to_sheet(values: list):
    ws = get_worksheet()
    ws.append_row(values, value_input_option="USER_ENTERED")


# ================== BOT ЛОГИКА ==================

FIELDS = [
    "name",
    "type",
    "origin",
    "description",
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["step"] = 0

    await update.message.reply_text(
        "Добавляем новый камень.\n\n"
        "Шаг 1 из 4.\n"
        "Название камня:"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    step = context.user_data.get("step", 0)

    if step < len(FIELDS):
        context.user_data[FIELDS[step]] = text
        context.user_data["step"] = step + 1

    step = context.user_data["step"]

    if step == 1:
        await update.message.reply_text(
            "Шаг 2 из 4.\n"
            "Тип камня:"
        )

    elif step == 2:
        await update.message.reply_text(
            "Шаг 3 из 4.\n"
            "Происхождение:"
        )

    elif step == 3:
        await update.message.reply_text(
            "Шаг 4 из 4.\n"
            "Описание:"
        )

    elif step == 4:
        row = [context.user_data.get(f, "") for f in FIELDS]

        append_to_sheet(row)

        context.user_data.clear()
        context.user_data["step"] = 0

        await update.message.reply_text(
            "Записано в таблицу.\n\n"
            "Можно добавлять следующий камень.\n"
            "Введи название:"
        )


# ================== MAIN ==================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
