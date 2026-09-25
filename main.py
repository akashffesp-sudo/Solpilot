import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set!")

app_flask = Flask(__name__)
@app_flask.route('/')
def home():
    return "SolPilot PRO LIVE - Bot is running!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 SolPilot PRO is LIVE!\n\n"
        "✅ Bot connected successfully\n"
        "/start - Start bot\n"
        "/help - Help menu"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("SolPilot PRO Help:\nBot is online and working!")

def run_flask():
    app_flask.run(host='0.0.0.0', port=10000)

def main():
    print("SolPilot PRO Starting...")
    # Start Flask in background
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Build bot - NEW VERSION (FIXED)
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    
    print("SolPilot PRO LIVE")
    app.run_polling()

if __name__ == '__main__':
    main()
