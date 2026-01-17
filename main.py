import logging
import os

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import gspread
from oauth2client.service_account import ServiceAccountCredentials


# ================== НАСТРОЙКИ ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")

GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME")

# НИКАКИХ RuntimeError. Если что-то не задано — gspread сам упадёт.


# ================== ЛОГИ ==================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ================== GOOGLE SHEETS ==================

def get_worksheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_dict = eval(GOOGLE_CREDENTIALS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)
    return sheet.worksheet(SHEET_NAME)


def append_to_sheet(values: list):
    ws = get_worksheet()
    ws.append_row(values, value_input_option="USER_ENTERED")


# ================== BOT ЛОГИКА ==================

USER_DATA_KEYS = [
    "name",
    "type",
    "origin",
    "description",
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["step"] = 0

    await update.message.reply_text(
        "Привет. Давай добавим новый камень.\n\n"
        "Шаг 1 из 4.\n"
        "Напиши название камня."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    step = context.user_data.get("step", 0)

    if step < len(USER_DATA_KEYS):
        key = USER_DATA_KEYS[step]
        context.user_data[key] = text
        context.user_data["step"] = step + 1

    step = context.user_data["step"]

    if step == 1:
        await update.message.reply_text(
            "Шаг 2 из 4.\n"
            "Тип камня (драгоценный / полудрагоценный / минерал и т.д.)"
        )

    elif step == 2:
        await update.message.reply_text(
            "Шаг 3 из 4.\n"
            "Происхождение (страна, регион, месторождение)"
        )

    elif step == 3:
        await update.message.reply_text(
            "Шаг 4 из 4.\n"
            "Краткое описание камня"
        )

    elif step == 4:
        values = [
            context.user_data.get("name", ""),
            context.user_data.get("type", ""),
            context.user_data.get("origin", ""),
            context.user_data.get("description", ""),
        ]

        append_to_sheet(values)

        context.user_data.clear()

        await update.message.reply_text(
            "Готово. Камень добавлен в таблицу.\n\n"
            "Можно начинать новый ввод.\n"
            "Напиши название следующего камня."
        )

        context.user_data["step"] = 0


# ================== MAIN ==================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
