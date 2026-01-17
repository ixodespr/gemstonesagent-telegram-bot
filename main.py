import os
import json
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# -------------------------
# ЛОГИ
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# -------------------------
# ENV
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")

if not all([
    BOT_TOKEN,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_NAME,
]):
    raise RuntimeError("Не заданы все ENV переменные")

# -------------------------
# GOOGLE SCOPES
# -------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# -------------------------
# STATES
# -------------------------
ASK_NAME, ASK_WEIGHT, ASK_COMMENT = range(3)


# -------------------------
# GOOGLE
# -------------------------
def get_sheets_service():
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_SERVICE_ACCOUNT_JSON),
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


# -------------------------
# HANDLERS
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Добавление нового камня.\n\n"
        "Шаги:\n"
        "1. Название\n"
        "2. Вес\n"
        "3. Комментарий\n\n"
        "Введи название камня."
    )
    return ASK_NAME


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Принято. Укажи вес камня.")
    return ASK_WEIGHT


async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["weight"] = update.message.text.strip()
    await update.message.reply_text("Добавь комментарий.")
    return ASK_COMMENT


async def ask_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comment"] = update.message.text.strip()

    try:
        sheets = get_sheets_service()

        row = [
            datetime.utcnow().isoformat(),
            context.user_data.get("name"),
            context.user_data.get("weight"),
            context.user_data.get("comment"),
        ]

        logging.info(f"Appending row: {row}")

        sheets.spreadsheets().values().append(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{GOOGLE_SHEET_NAME}!A:D",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        await update.message.reply_text(
            "Готово.\n"
            "Данные добавлены в таблицу.\n\n"
            "Можно добавлять следующий камень.\n"
            "Введи название."
        )

    except Exception as e:
        logging.exception("SHEETS ERROR")
        await update.message.reply_text(
            "Ошибка при записи в таблицу.\n\n"
            f"{str(e)[:300]}"
        )
        context.user_data.clear()
        return ConversationHandler.END

    # очистка кеша и новый круг
    context.user_data.clear()
    return ASK_NAME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Процесс отменён.")
    return ConversationHandler.END


# -------------------------
# MAIN
# -------------------------
def main():
    logging.info("Bot started")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_weight)],
            ASK_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()
