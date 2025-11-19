# app.py
import os
import asyncio
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Load .env
load_dotenv()

TOKEN = os.getenv("TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise Exception("未设置 TOKEN 环境变量，请在 .env 中添加 TOKEN=your_token 或在平台环境变量中设置")

PORT = int(os.getenv("PORT", "8080"))
RAILWAY_STATIC_URL = os.getenv("RAILWAY_STATIC_URL")  # e.g. xxxxx.up.railway.app
if not RAILWAY_STATIC_URL:
    raise Exception("未设置 RAILWAY_STATIC_URL 环境变量，请在平台 Variables 中添加 RAILWAY_STATIC_URL=xxxxx.up.railway.app")

DATA_FILE = "attendance_records.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def load_records():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_records(records):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

records = load_records()

def get_keyboard():
    keyboard = [
        [InlineKeyboardButton("上班 / Start Work", callback_data="start_work"),
         InlineKeyboardButton("下班 / End Work", callback_data="end_work")],
        [InlineKeyboardButton("开始早餐 / Start Breakfast", callback_data="breakfast_start"),
         InlineKeyboardButton("结束早餐 / End Breakfast", callback_data="breakfast_end")],
        [InlineKeyboardButton("开始午餐 / Start Lunch", callback_data="lunch_start"),
         InlineKeyboardButton("结束午餐 / End Lunch", callback_data="lunch_end")],
        [InlineKeyboardButton("开始晚餐 / Start Dinner", callback_data="dinner_start"),
         InlineKeyboardButton("结束晚餐 / End Dinner", callback_data="dinner_end")],
        [InlineKeyboardButton("查看记录 / Report", callback_data="report")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    username = query.from_user.username or query.from_user.first_name or user_id
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_id not in records:
        records[user_id] = {"username": username, "work": {}, "meals": {}}

    data = query.data
    text = ""

    if data == "start_work":
        records[user_id]["work"]["start"] = now
        text = f"{username} 上班打卡成功 ✅\n时间: {now}"
    elif data == "end_work":
        records[user_id]["work"]["end"] = now
        text = f"{username} 下班打卡成功 ✅\n时间: {now}"
    elif data.endswith("_start"):
        meal = data.split("_")[0]
        records[user_id]["meals"].setdefault(meal, {})["start"] = now
        text = f"{username} {meal} 开始打卡 ✅\n时间: {now}"
    elif data.endswith("_end"):
        meal = data.split("_")[0]
        meal_rec = records[user_id]["meals"].get(meal, {})
        if "start" not in meal_rec:
            text = f"没有记录到 {meal} 开始时间，请先点击 开始{meal}。"
        else:
            meal_rec["end"] = now
            # calculate duration
            try:
                fmt = "%Y-%m-%d %H:%M:%S"
                t0 = datetime.strptime(meal_rec["start"], fmt)
                t1 = datetime.strptime(meal_rec["end"], fmt)
                delta = t1 - t0
                mins = int(delta.total_seconds() // 60)
                text = f"{username} {meal} 结束 ✅\n用时: {mins} 分钟"
            except Exception:
                text = f"{username} {meal} 结束 ✅\n时间: {now}"
    elif data == "report":
        r = records.get(user_id)
        if not r:
            text = "没有记录。"
        else:
            w = r.get("work", {})
            msg = [f"上班: {w.get('start','未打卡')}", f"下班: {w.get('end','未打卡')}", "---"]
            for meal in ["breakfast","lunch","dinner"]:
                m = r.get("meals", {}).get(meal, {})
                msg.append(f"{meal}: {m.get('start','-')} - {m.get('end','-')}")
            text = "\n".join(msg)
    else:
        text = "未知操作"

    save_records(records)
    try:
        await query.edit_message_text(text, reply_markup=get_keyboard())
    except Exception:
        # fallback to sending a new message
        await query.message.reply_text(text, reply_markup=get_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("欢迎使用考勤与用餐打卡机器人 ✅", reply_markup=get_keyboard())

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    await app.initialize()
    await app.start()

    webhook_url = f"https://{RAILWAY_STATIC_URL}/{TOKEN}"
    logger.info("Setting webhook to %s", webhook_url)
    await app.bot.set_webhook(webhook_url)

    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=webhook_url
    )

    logger.info("Bot started. webhook_url=%s", webhook_url)
    await app.idle()

if __name__ == '__main__':
    asyncio.run(main())
