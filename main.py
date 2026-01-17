import os
import json
import logging

import gspread
from google.oauth2.service_account import Credentials

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------------
# LOGGING
# -------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# -------------------------
# ENV — СТРОГО КАК В РАБОЧЕЙ ВЕРСИИ
# -------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не задан")

if not SPREADSHEET_ID:
    raise RuntimeError("SPREADSHEET_ID не задан")

if not GOOGLE_SERVICE_ACCOUNT_JSON:
    raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON не задан")

# -------------------------
# GOOGLE SHEETS
# -------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES,
)

gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# -------------------------
# DATA STRUCTURE
# -------------------------
FIELDS = [
    ("name", "Название камня"),
    ("color", "Цвет"),
    ("shape", "Форма"),
    ("size_ct", "Размер (ct)"),
    ("origin", "Происхождение"),
    ("clarity", "Чистота"),
    ("price", "Цена"),
]

# -------------------------
# HANDLERS
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["step"] = 0

    await update.message.reply_text(
        "Добавляем новый камень.\n"
        "Отвечай по порядку.\n\n"
        f"{FIELDS[0][1]}:"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step", 0)

    if step >= len(FIELDS):
        await update.message.reply_text("Сессия сломалась. Напиши /start")
        context.user_data.clear()
        return

    key, label = FIELDS[step]
    context.user_data[key] = update.message.text.strip()
    context.user_data["step"] = step + 1

    # Если есть следующий вопрос
    if context.user_data["step"] < len(FIELDS):
        next_label = FIELDS[context.user_data["step"]][1]
        await update.message.reply_text(f"{next_label}:")
        return

    # -------------------------
    # SAVE TO GOOGLE SHEET
    # -------------------------
    row = [
        context.user_data.get("name", ""),
        context.user_data.get("color", ""),
        context.user_data.get("shape", ""),
        context.user_data.get("size_ct", ""),
        context.user_data.get("origin", ""),
        context.user_data.get("clarity", ""),
        context.user_data.get("price", ""),
    ]

    sheet.append_row(row, value_input_option="USER_ENTERED")

    await update.message.reply_text(
        "Готово. Камень записан в таблицу.\n\n"
        "Для добавления следующего — /start"
    )

    context.user_data.clear()

# -------------------------
# MAIN
# -------------------------
def main():
    logging.info("BOT STARTING")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logging.info("BOT POLLING")
    app.run_polling()

if __name__ == "__main__":
    main()
