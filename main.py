import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
BOT_TOKEN=os.environ.get("BOT_TOKEN")
RPC_URL=os.environ.get("RPC_URL")
AI_KEY=os.environ.get("AI_KEY")
ADMIN_ID=6811023733
client=OpenAI(api_key=AI_KEY)
USERS={}
async def start(update,context):
    USERS[update.effective_user.id]=USERS.get(update.effective_user.id,{"trades":0})
    await update.message.reply_text("✈️ SolPilot LIVE!\n\nCommands:\n/buy BONK 0.1\n/sell BONK 0.1\n/admin_stats\n\nChat with me: how to buy BONK?")
async def buy(update,context):
    if update.effective_user.id in USERS: USERS[update.effective_user.id]["trades"]+=1
    arg=" ".join(context.args) if context.args else "BONK"
    await update.message.reply_text(f"✅ BUY {arg} logged! Jupiter swap ready.")
async def admin_stats(update,context):
    if update.effective_user.id!=ADMIN_ID:
        await update.message.reply_text("Admin only");return
    await update.message.reply_text(f"📊 Users: {len(USERS)}\nTrades: {sum(u['trades'] for u in USERS.values())}")
async def ai(update,context):
    if update.message.text.startswith("/"):return
    try:
        r=client.chat.completions.create(model="gpt-4o-mini",messages=[{"role":"system","content":"You are SolPilot Solana trader, helpful short"},{"role":"user","content":update.message.text}])
        await update.message.reply_text(r.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text("AI busy")
def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("buy",buy))
    app.add_handler(CommandHandler("sell",buy))
    app.add_handler(CommandHandler("admin_stats",admin_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,ai))
    app.run_polling()
if __name__=="__main__":
    main()
