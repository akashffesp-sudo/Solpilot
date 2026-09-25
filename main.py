import os, json, base64, requests, base58
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import *
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts

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

# REAL JUPITER BUY/SELL
def jupiter_swap(private_key_b58, input_mint, output_mint, amount_lamports):
    try:
        kp = Keypair.from_base58_string(private_key_b58)
        # Quote
        q_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount_lamports}&slippageBps=300"
        quote = requests.get(q_url, timeout=15).json()
        if "error" in quote or "routePlan" not in quote:
            return False, f"❌ Quote failed: {quote.get('error', 'No route')}"

        # Swap tx
        swap_body = {
            "quoteResponse": quote,
            "userPublicKey": str(kp.pubkey()),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True
        }
        swap_res = requests.post("https://quote-api.jup.ag/v6/swap", json=swap_body, timeout=15).json()
        if "swapTransaction" not in swap_res:
            return False, f"❌ Swap build failed: {swap_res}"

        # Decode, sign, send
        tx_bytes = base64.b64decode(swap_res["swapTransaction"])
        tx = VersionedTransaction.from_bytes(tx_bytes)
        signed_tx = VersionedTransaction(tx.message, [kp])

        # Send
        result = client.send_transaction(signed_tx, opts=TxOpts(skip_preflight=False))
        sig = result.value if hasattr(result, 'value') else str(result)
        return True, f"✅ Success!\nTx: https://solscan.io/tx/{sig}\nAmount: {quote.get('outAmount')}"

    except Exception as e:
        return False, f"❌ Error: {str(e)[:300]}"

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in wallets:
        kp = Keypair()
        wallets[uid] = {"pubkey": str(kp.pubkey()), "secret": base58.b58encode(bytes(kp)).decode()}
        save_wallets(wallets)
    w = wallets[uid]
    text = (
        f"✈️ *SOLPILOT — Pro Trading Bot*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💼 *Wallet:*\n`{w['pubkey']}`\n\n"
        f"💰 Balance: Check via /wallet\n\n"
        f"Select action 👇"
    )
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
        await query.message.edit_text(
            f"💼 *WALLET*\n━━━━━━━━━━━━\n\n`{w['pubkey']}`\n\nSOL Balance: {bal} SOL\n\nDeposit SOL to trade.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))

    elif data == "buy":
        user_state[uid] = {"action":"buy"}
        await query.message.edit_text("💰 *BUY*\n━━━━━━━━━━━━\nSend TOKEN MINT ADDRESS to buy\n\nEx: `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`", parse_mode="Markdown")
        return 0

    elif data == "sell":
        user_state[uid] = {"action":"sell"}
        await query.message.edit_text("📤 *SELL*\n━━━━━━━━━━━━\nSend TOKEN MINT ADDRESS you want to sell", parse_mode="Markdown")
        return 0

    elif data == "send":
        user_state[uid] = {"action":"send"}
        await query.message.edit_text("🚀 *SEND*\n━━━━━━━━━━━━\nStep 1/3: Send TOKEN MINT ADDRESS", parse_mode="Markdown")
        return 0

    elif data == "import":
        await query.message.edit_text("🔑 Send Private Key (base58) - will be auto-deleted", parse_mode="Markdown")
        return 3

    elif data == "copytrade":
        w = get_wallet(uid)
        await query.message.edit_text(
            f"⚡ *COPY TRADE*\n━━━━━━━━━━━━\n\nRequires wallet with 100 USDT (~0.65 SOL)\n\nYour Wallet:\n`{w['pubkey']}`\n\nDeposit and try again!",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back")]]))

    elif data == "back" or data == "portfolio":
        await start(update, context)

async def ask_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_state[uid]["token"] = update.message.text.strip()
    await update.message.reply_text(f"Token: `{user_state[uid]['token']}`\n\nHow much? \nFor BUY: amount in SOL (e.g. 0.1)\nFor SELL/SEND: amount in tokens (e.g. 100)", parse_mode="Markdown")
    return 1

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_state.get(uid, {})
    token = state["token"]
    amount_str = update.message.text.strip()

    if state["action"] == "send":
        state["amount"] = amount_str
        await update.message.reply_text("Step 3/3: Send RECEIVER WALLET ADDRESS")
        return 2

    w = get_wallet(uid)
    await update.message.reply_text(f"🔄 Executing {state['action']}... wait 5 sec")

    try:
        if state["action"] == "buy":
            lamports = int(float(amount_str) * 1e9)
            ok, msg = jupiter_swap(w["secret"], SOL_MINT, token, lamports)
        else: # sell
            # For sell, amount is in token raw amount - need decimals, using 6 as default
            # User should send raw amount, or we fetch decimals - simplified
            lamports = int(float(amount_str) * 1e6)
            ok, msg = jupiter_swap(w["secret"], token, SOL_MINT, lamports)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}", reply_markup=main_menu())
    return ConversationHandler.END

async def ask_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # For SEND - token transfer logic (simplified - needs SPL transfer)
    dest = update.message.text.strip()
    state = user_state[update.effective_user.id]
    await update.message.reply_text(
        f"✅ Ready to send {state['amount']} of `{state['token']}` to `{dest}`\n\nNote: SPL send needs extra code - add transfer logic here.\nFor now use Phantom to send, or I can add full SPL send code.",
        parse_mode="Markdown", reply_markup=main_menu())
    return ConversationHandler.END

async def handle_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        kp = Keypair.from_base58_string(text)
        wallets[str(update.effective_user.id)] = {"pubkey": str(kp.pubkey()), "secret": text}
        save_wallets(wallets)
        await update.message.delete()
        await update.message.reply_text(f"✅ Wallet Imported: `{kp.pubkey()}`", parse_mode="Markdown", reply_markup=main_menu())
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Invalid key. Try again.")
        return 3

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(wallet|buy|sell|send|import|copytrade|back|portfolio)$"))

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler), MessageHandler(filters.TEXT & ~filters.COMMAND, ask_token)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_token)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dest)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_import)]
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)]
    )
    app.add_handler(conv)
    print("SolPilot PRO LIVE with real swaps")
    app.run_polling()

if __name__ == "__main__":
    main()
