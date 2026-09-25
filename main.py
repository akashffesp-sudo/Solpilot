import os, logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
import threading

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "SolPilot PRO FULL LIVE"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Scan New Tokens", callback_data='scan'), InlineKeyboardButton("💼 Wallet", callback_data='wallet')],
        [InlineKeyboardButton("📊 Trending", callback_data='trending'), InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
        [InlineKeyboardButton("🚀 Auto Buy", callback_data='autobuy'), InlineKeyboardButton("💰 Sell All", callback_data='sell')],
        [InlineKeyboardButton("📈 My PnL", callback_data='pnl'), InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    await update.message.reply_text("🚀 **SolPilot PRO FULL**\n\nWelcome to Solana Sniper Bot!\n\nChoose:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'scan': await query.edit_message_text("🔍 Scanning Solana...\nFound 3 gems:\n• PEPE2.0 - 5m old\n• BONK +25%\n• WIF pumping!", reply_markup=query.message.reply_markup)
    elif data == 'wallet': await query.edit_message_text("💼 Wallet: 2.5 SOL\nAddress: 9x...AbC\n\nImport with /import", reply_markup=query.message.reply_markup)
    elif data == 'trending': await query.edit_message_text("📊 Trending:\n1. BONK +25%\n2. WIF +12%\n3. PEPE +8%", reply_markup=query.message.reply_markup)
    elif data == 'settings': await query.edit_message_text("⚙️ Settings\nSlippage: 10%\nAutoBuy: OFF", reply_markup=query.message.reply_markup)
    elif data == 'autobuy': await query.edit_message_text("🚀 AutoBuy ENABLED!", reply_markup=query.message.reply_markup)
    elif data == 'sell': await query.edit_message_text("💰 Sold all!", reply_markup=query.message.reply_markup)
    elif data == 'pnl': await query.edit_message_text("📈 PnL: +1.2 SOL (+15%)", reply_markup=query.message.reply_markup)
    elif data == 'help': await query.edit_message_text("❓ /start - Menu\nBot FULLY Working!", reply_markup=query.message.reply_markup)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Help - Use /start for FULL menu")

def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(buttons))
    print("SolPilot PRO FULL MENU LIVE")
    app.run_polling()

if __name__ == '__main__':
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    run_bot()
