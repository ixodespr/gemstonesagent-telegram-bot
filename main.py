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
from googleapiclient.http import MediaInMemoryUpload

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
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")

if not all([
    BOT_TOKEN,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_NAME,
]):
    raise RuntimeError("Не заданы все ENV переменные")

# -------------------------
# GOOGLE SCOPES
# -------------------------
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

# -------------------------
# STATES
# -------------------------
WAIT_PHOTO, ASK_NAME, ASK_WEIGHT, ASK_COMMENT = range(4)


# -------------------------
# GOOGLE SERVICES
# -------------------------
def get_google_services():
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_SERVICE_ACCOUNT_JSON),
        scopes=SCOPES,
    )
    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)
    return drive, sheets


# -------------------------
# HANDLERS
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добавление нового камня.\n\n"
        "Порядок:\n"
        "1. Фото камня\n"
        "2. Название\n"
        "3. Вес\n"
        "4. Комментарий\n\n"
        "Пришли фото камня."
    )
    return WAIT_PHOTO


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        drive, _ = get_google_services()

        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        file_bytes = await tg_file.download_as_bytearray()

        filename = f"stone_{datetime.utcnow().isoformat()}.jpg"

        media = MediaInMemoryUpload(
            file_bytes,
            mimetype="image/jpeg",
            resumable=False,
        )

        logging.info(f"Uploading photo to Drive folder {GOOGLE_DRIVE_FOLDER_ID}")

        uploaded = drive.files().create(
            media_body=media,
            body={
                "name": filename,
                "parents": [GOOGLE_DRIVE_FOLDER_ID],
            },
            fields="id",
        ).execute()

        context.user_data["photo_id"] = uploaded["id"]

        logging.info(f"Photo uploaded successfully, id={uploaded['id']}")

        await update.message.reply_text(
            "Фото сохранено.\n"
            "Теперь введи название камня."
        )
        return ASK_NAME

    except Exception as e:
        logging.exception("DRIVE UPLOAD ERROR")

        await update.message.reply_text(
            "Ошибка при сохранении фото в Google Drive.\n\n"
            f"{str(e)[:300]}"
        )
        context.user_data.clear()
        return ConversationHandler.END


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
        _, sheets = get_google_services()

        row = [
            datetime.utcnow().isoformat(),
            context.user_data.get("name"),
            context.user_data.get("weight"),
            context.user_data.get("comment"),
            context.user_data.get("photo_id"),
        ]

        logging.info(f"Appending row to sheet: {row}")

        result = sheets.spreadsheets().values().append(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{GOOGLE_SHEET_NAME}!A:E",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        logging.info(f"SHEETS SUCCESS: {result}")

        await update.message.reply_text(
            "Готово.\n\n"
            "Фото сохранено в Google Drive.\n"
            "Данные добавлены в таблицу."
        )

    except Exception as e:
        logging.exception("SHEETS WRITE ERROR")

        await update.message.reply_text(
            "Фото сохранено, но возникла ошибка при записи в таблицу.\n\n"
            f"{str(e)[:300]}"
        )

    finally:
        context.user_data.clear()
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Процесс добавления отменён.")
    return ConversationHandler.END


# -------------------------
# MAIN
# -------------------------
def main():
    logging.info("Bot starting")

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_PHOTO: [MessageHandler(filters.PHOTO, handle_photo)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_weight)],
            ASK_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
