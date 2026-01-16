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

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

# Состояния диалога
WAIT_PHOTO, ASK_NAME, ASK_WEIGHT, ASK_COMMENT = range(4)


def get_google_services():
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_SERVICE_ACCOUNT_JSON),
        scopes=SCOPES,
    )
    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)
    return drive, sheets


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет.\n\n"
        "Я помогу зафиксировать новый камень.\n\n"
        "Порядок действий:\n"
        "1. Загрузи фото камня\n"
        "2. Заполни информацию\n"
        "3. Данные сохранятся в таблицу\n\n"
        "Начинай. Пришли фото."
    )
    return WAIT_PHOTO


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drive, _ = get_google_services()

    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_bytes = await file.download_as_bytearray()

    media = MediaInMemoryUpload(
        file_bytes,
        mimetype="image/jpeg",
        resumable=False,
    )

    filename = f"stone_{datetime.utcnow().isoformat()}.jpg"

    uploaded = drive.files().create(
        media_body=media,
        body={
            "name": filename,
            "parents": [DRIVE_FOLDER_ID],
        },
        fields="id",
    ).execute()

    context.user_data["photo_id"] = uploaded["id"]

    await update.message.reply_text(
        "Фото сохранено.\n\n"
        "Теперь укажи название камня."
    )
    return ASK_NAME


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Принял. Укажи вес камня.")
    return ASK_WEIGHT


async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["weight"] = update.message.text
    await update.message.reply_text("Добавь комментарий или описание.")
    return ASK_COMMENT


async def ask_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comment"] = update.message.text

    _, sheets = get_google_services()

    row = [
        datetime.utcnow().isoformat(),
        context.user_data["name"],
        context.user_data["weight"],
        context.user_data["comment"],
        context.user_data["photo_id"],
    ]

    sheets.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range="A1",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()

    await update.message.reply_text(
        "Готово.\n\n"
        "Камень сохранён:\n"
        f"Название: {context.user_data['name']}\n"
        f"Вес: {context.user_data['weight']}\n\n"
        "Можно добавлять следующий камень через /start"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Процесс сброшен.")
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_PHOTO: [MessageHandler(filters.PHOTO, handle_photo)],
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
