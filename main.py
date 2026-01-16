Python 3.14.2 (v3.14.2:df793163d58, Dec  5 2025, 12:18:06) [Clang 16.0.0 (clang-1600.0.26.6)] on darwin
Enter "help" below or click "Help" above for more information.
import os
import json
import logging
import tempfile

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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
# ENV
# -------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

for var in [
    TELEGRAM_TOKEN,
    SPREADSHEET_ID,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_DRIVE_FOLDER_ID,
]:
    if not var:
        raise RuntimeError("Missing env variables")

# -------------------------
# GOOGLE AUTH
# -------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES,
)

gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

drive_service = build("drive", "v3", credentials=creds)

# -------------------------
# STATES
# -------------------------
FIELDS = [
    ("name", "Название камня?"),
    ("color", "Цвет?"),
    ("shape", "Форма?"),
    ("size_ct", "Размер (ct)?"),
    ("origin", "Происхождение?"),
    ("price", "Цена?"),
]

# -------------------------
# COMMANDS
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот добавления камней.\n"
        "Команда: /add"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["step"] = 0
    context.user_data["data"] = {}
    await update.message.reply_text(FIELDS[0][1])

# -------------------------
# TEXT HANDLER
# -------------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")

    if step is None or step >= len(FIELDS):
        return

    key, _ = FIELDS[step]
    context.user_data["data"][key] = update.message.text.strip()
    context.user_data["step"] += 1

    if context.user_data["step"] < len(FIELDS):
        await update.message.reply_text(
            FIELDS[context.user_data["step"]][1]
        )
    else:
        await update.message.reply_text("Пришли фото камня.")

# -------------------------
# PHOTO HANDLER
# -------------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != len(FIELDS):
        await update.message.reply_text("Фото сейчас не нужно.")
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()

    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        await file.download_to_drive(tmp.name)

        image_url = upload_to_drive(tmp.name)

    save_to_sheet(context.user_data["data"], image_url)
    context.user_data.clear()

    await update.message.reply_text("Камень сохранён.")

# -------------------------
# GOOGLE DRIVE
# -------------------------
def upload_to_drive(path: str) -> str:
    metadata = {
        "name": os.path.basename(path),
        "parents": [GOOGLE_DRIVE_FOLDER_ID],
    }

    media = MediaFileUpload(path, mimetype="image/jpeg")

    file = drive_service.files().create(
        body=metadata,
        media_body=media,
        fields="id",
    ).execute()
... 
...     drive_service.permissions().create(
...         fileId=file["id"],
...         body={"type": "anyone", "role": "reader"},
...     ).execute()
... 
...     return f"https://drive.google.com/uc?id={file['id']}"
... 
... # -------------------------
... # GOOGLE SHEETS
... # -------------------------
... def save_to_sheet(data: dict, image_url: str):
...     sheet.append_row([
...         data.get("name"),
...         data.get("color"),
...         data.get("shape"),
...         data.get("size_ct"),
...         data.get("origin"),
...         data.get("price"),
...         image_url,
...     ])
... 
... # -------------------------
... # MAIN
... # -------------------------
... def main():
...     app = Application.builder().token(TELEGRAM_TOKEN).build()
... 
...     app.add_handler(CommandHandler("start", start))
...     app.add_handler(CommandHandler("add", add))
...     app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
...     app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
... 
...     app.run_polling()
... 
... 
... if __name__ == "__main__":
...     main()
