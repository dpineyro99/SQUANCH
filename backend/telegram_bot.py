import os
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SQUANCH_BACKEND_URL = "http://127.0.0.1:8000/chat"
CHAT_ID_FILE = "telegram_chat_id.txt"


def save_chat_id(chat_id: int):
    with open(CHAT_ID_FILE, "w") as f:
        f.write(str(chat_id))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.effective_chat.id)
    await update.message.reply_text("SQUANCH online desde Telegram. Chat ID guardado para recordatorios.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    save_chat_id(update.effective_chat.id)

    await update.message.reply_text("Recibido. SQUANCH está trabajando...")

    try:
        response = requests.post(
            SQUANCH_BACKEND_URL,
            json={"message": text},
            timeout=300
        )

        data = response.json()
        reply = data.get("response", "No recibí respuesta del backend.")

        if len(reply) > 3900:
            reply = reply[-3900:]

        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(
            f"Error conectando con SQUANCH backend: {e}"
        )


def main():
    if not TOKEN:
        raise ValueError("Falta TELEGRAM_BOT_TOKEN en .env")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("SQUANCH Telegram bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
