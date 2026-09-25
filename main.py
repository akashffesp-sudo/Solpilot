import os, json, base64, requests, base58, threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "SolPilot LIVE"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RPC = os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
SOL_MINT = "So11111111111111111111111111111111111111112"

wallets = {}
WALLETS_FILE = "wallets.json"
def load_w():
    if os.path.exists(WALLETS_FILE):
        try:
            with open(WALLETS_FILE,"r") as f: return json.load(f)
        except: return {}
    return {}
def save_w(d):
    with open(WALLETS_FILE,"w") as f: json.dump(d,f)
wallets = load_w()
user_state = {}

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 BUY", callback_data="buy"), InlineKeyboardButton("📤 SELL", callback_data="sell")],
        [InlineKeyboardButton("💼 Wallet", callback_data="wallet"), InlineKeyboardButton("🔑 Import", callback_data="import")],
        [InlineKeyboardButton("🔙 Start", callback_data="start")]
    ])

def get_balance(pubkey):
    try:
        r = requests.post(RPC, json={"jsonrpc":"2.0","id":1,"method":"getBalance","params":[pubkey]}, timeout=10).json()
        return f"{r['result']['value']/1e9:.4f}"
    except: return "0"

def jupiter_swap(pk_b58, in_mint, out_mint, amt):
    try:
        kp = Keypair.from_base58_string(pk_b58)
        q = requests.get(f"https://quote-api.jup.ag/v6/quote?inputMint={in_mint}&outputMint={out_mint}&amount={amt}&slippageBps=300", timeout=15).json()
        if "routePlan" not in q: return False, "❌ No route found"
        body = {"quoteResponse": q, "userPublicKey": str(kp.pubkey()), "wrapAndUnwrapSol": True}
        s = requests.post("https://quote-api.jup.ag/v6/swap", json=body, timeout=15).json()
        if "swapTransaction" not in s: return False, "❌ Swap build fail"
        tx = VersionedTransaction.from_bytes(base64.b64decode(s["swapTransaction"]))
        signed = VersionedTransaction(tx.message, [kp])
        b64tx = base64.b64encode(bytes(signed)).decode()
        send = requests.post(RPC, json={"jsonrpc":"2.0","id":1,"method":"sendTransaction","params":[b64tx, {"skipPreflight": False}]}, timeout=15).json()
        sig = send.get("result", str(send))
        return True, f"✅ Success!\nhttps://solscan.io/tx/{sig}"
    except Exception as e:
        return False, f"❌ {str(e)[:350]}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in wallets:
        kp = Keypair()
        wallets[uid] = {"pubkey": str(kp.pubkey()), "secret": base58.b58encode(bytes(kp)).decode()}
        save_w(wallets)
    w = wallets[uid]
    txt = f"✈️ *SOLPILOT Pro*\n\n💼 `{w['pubkey']}`\nBal: {get_balance(w['pubkey'])} SOL"
    if update.message:
        await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=menu())
    else:
        await update.callback_query.message.edit_text(txt, parse_mode="Markdown", reply_markup=menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data
    if data == "wallet":
        w = wallets[str(uid)]
        await q.message.edit_text(f"💼 `{w['pubkey']}`\nBal: {get_balance(w['pubkey'])} SOL", parse_mode="Markdown", reply_markup=menu())
    elif data == "buy":
        user_state[uid] = "buy_token"
        await q.message.edit_text("💰 Send TOKEN ADDRESS to BUY")
    elif data == "sell":
        user_state[uid] = "sell_token"
        await q.message.edit_text("📤 Send TOKEN ADDRESS to SELL")
    elif data == "import":
        user_state[uid] = "import"
        await q.message.edit_text("🔑 Send Private Key (base58)")
    else:
        await start(update, context)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text.strip()
    state = user_state.get(uid)

    if state == "import":
        try:
            kp = Keypair.from_base58_string(txt)
            wallets[str(uid)] = {"pubkey": str(kp.pubkey()), "secret": txt}
            save_w(wallets)
            user_state.pop(uid, None)
            try: await update.message.delete()
            except: pass
            await update.message.reply_text(f"✅ Imported `{kp.pubkey()}`", parse_mode="Markdown", reply_markup=menu())
        except:
            await update.message.reply_text("❌ Invalid key")
        return

    if state == "buy_token":
        user_state[uid] = f"buy_amt_{txt}"
        await update.message.reply_text("Amount SOL? eg 0.1")
        return
    if state and str(state).startswith("buy_amt_"):
        token = str(state).replace("buy_amt_","")
        try:
            lam = int(float(txt)*1e9)
            w = wallets[str(uid)]
            await update.message.reply_text("🔄 Swapping...")
            ok, msg = jupiter_swap(w["secret"], SOL_MINT, token, lam)
            await update.message.reply_text(msg, reply_markup=menu())
        except Exception as e:
            await update.message.reply_text(f"❌ {e}", reply_markup=menu())
        user_state.pop(uid, None)
        return

    if state == "sell_token":
        user_state[uid] = f"sell_amt_{txt}"
        await update.message.reply_text("Amount tokens? eg 1000")
        return
    if state and str(state).startswith("sell_amt_"):
        token = str(state).replace("sell_amt_","")
        try:
            lam = int(float(txt)*1e6)
            w = wallets[str(uid)]
            await update.message.reply_text("🔄 Swapping...")
            ok, msg = jupiter_swap(w["secret"], token, SOL_MINT, lam)
            await update.message.reply_text(msg, reply_markup=menu())
        except Exception as e:
            await update.message.reply_text(f"❌ {e}", reply_markup=menu())
        user_state.pop(uid, None)
        return

    await start(update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("SolPilot PRO LIVE")
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    main()
