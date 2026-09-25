import os, json, base64, requests, base58, threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import *
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts

# Flask for Render free port fix
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "SolPilot LIVE - Bot Running"
def run_flask(): flask_app.run(host='0.0.0.0', port=10000)

# Config
SOL_MINT = "So11111111111111111111111111111111111111112"
RPC_URL = os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
client = Client(RPC_URL)

WALLETS_FILE = "wallets.json"
wallets = {}
user_state = {}

def load_wallets():
    if os.path.exists(WALLETS_FILE):
        with open(WALLETS_FILE, "r") as f: return json.load(f)
    return {}
def save_wallets(d):
    with open(WALLETS_FILE, "w") as f: json.dump(d,f)
wallets = load_wallets()

def get_wallet(uid): return wallets.get(str(uid))

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 BUY", callback_data="buy"), InlineKeyboardButton("📤 SELL", callback_data="sell")],
        [InlineKeyboardButton("💼 Wallet", callback_data="wallet"), InlineKeyboardButton("🔑 Import Wallet", callback_data="import")],
        [InlineKeyboardButton("🚀 Send", callback_data="send"), InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")],
        [InlineKeyboardButton("⚡ Copy Trade", callback_data="copytrade")]
    ])

def jupiter_swap(private_key_b58, input_mint, output_mint, amount_lamports):
    try:
        kp = Keypair.from_base58_string(private_key_b58)
        q_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount_lamports}&slippageBps=300"
        quote = requests.get(q_url, timeout=15).json()
        if "error" in quote or "routePlan" not in quote:
            return False, f"❌ Quote failed: {quote.get('error', 'No route')}"
        swap_body = {
            "quoteResponse": quote,
            "userPublicKey": str(kp.pubkey()),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True
        }
        swap_res = requests.post("https://quote-api.jup.ag/v6/swap", json=swap_body, timeout=15).json()
        if "swapTransaction" not in swap_res:
            return False, f"❌ Swap failed: {swap_res}"
        tx_bytes = base64.b64decode(swap_res["swapTransaction"])
        tx = VersionedTransaction.from_bytes(tx_bytes)
        signed_tx = VersionedTransaction(tx.message, [kp])
        result = client.send_transaction(signed_tx, opts=TxOpts(skip_preflight=False))
        sig = result.value if hasattr(result, 'value') else str(result)
        return True, f"✅ Success!\nTx: https://solscan.io/tx/{sig}"
    except Exception as e:
        return False, f"❌ Error: {str(e)[:400]}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in wallets:
        kp = Keypair()
        wallets[uid] = {"pubkey": str(kp.pubkey()), "secret": base58.b58encode(bytes(kp)).decode()}
        save_wallets(wallets)
    w = wallets[uid]
    text = f"✈️ *SOLPILOT — Pro Bot*\n━━━━━━━━━━━━\n\n💼 Wallet:\n`{w['pubkey']}`\n\nSelect action 👇"
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())
    else:
        await update.callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    if data == "wallet":
        w = get_wallet(uid)
        bal = "0.00"
        try:
            b = client.get_balance(w["pubkey"]) if w else None
            if b: bal = f"{b.value/1e9:.4f}"
        except: pass
        await query.message.edit_text(f"💼 *WALLET*\n`{w['pubkey']}`\nBalance: {bal} SOL", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif data == "buy":
        user_state[uid] = {"action":"buy"}
        await query.message.edit_text("💰 *BUY*\nSend TOKEN ADDRESS", parse_mode="Markdown")
        return 0
    elif data == "sell":
        user_state[uid] = {"action":"sell"}
        await query.message.edit_text("📤 *SELL*\nSend TOKEN ADDRESS", parse_mode="Markdown")
        return 0
    elif data == "send":
        user_state[uid] = {"action":"send"}
        await query.message.edit_text("🚀 *SEND*\nStep 1/3: Token Address", parse_mode="Markdown")
        return 0
    elif data == "import":
        await query.message.edit_text("🔑 Send Private Key", parse_mode="Markdown")
        return 3
    elif data == "copytrade":
        w = get_wallet(uid)
        await query.message.edit_text(f"⚡ *COPY TRADE*\nNeeds 100 USDT (~0.65 SOL)\nWallet: `{w['pubkey']}`\nDeposit and retry!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))
    elif data == "back" or data == "portfolio":
        await start(update, context)

async def ask_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_state[uid]["token"] = update.message.text.strip()
    await update.message.reply_text(f"Token: `{user_state[uid]['token']}`\nHow much? BUY: SOL amount (0.1) / SELL: token amount", parse_mode="Markdown")
    return 1

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_state.get(uid, {})
    token = state["token"]
    amount_str = update.message.text.strip()
    if state["action"] == "send":
        state["amount"] = amount_str
        await update.message.reply_text("Step 3/3: Receiver Address")
        return 2
    w = get_wallet(uid)
    await update.message.reply_text(f"🔄 Buying/Selling... wait 5 sec")
    try:
        if state["action"] == "buy":
            lamports = int(float(amount_str) * 1e9)
            ok, msg = jupiter_swap(w["secret"], SOL_MINT, token, lamports)
        else:
            lamports = int(float(amount_str) * 1e6)
            ok
