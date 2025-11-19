import json
import datetime
import os
import logging
import sys
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

DATA_FILE = "attendance_data.json"


def load_data():
    if not os.path.isfile(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("机器人已启动，可以使用：\n/checkin 上班\n/checkout 下班")


async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data = load_data()
    data.setdefault(user_id, {"name": user.full_name, "records": []})
    data[user_id]["records"].append({"type": "checkin", "time": now})
    save_data(data)

    await update.message.reply_text(f"上班打卡成功：{now}")


async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data = load_data()
    data.setdefault(user_id, {"name": user.full_name, "records": []})
    data[user_id]["records"].append({"type": "checkout", "time": now})
    save_data(data)

    await update.message.reply_text(f"下班打卡成功：{now}")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ 没找到 TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    logger.info("✅ Token 已加载")
    application = Application.builder().token(token).build()

    # 注册 handlers（你之前缺少的部分）
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("checkout", checkout))

    logger.info("🚀 机器人启动成功！")
    application.run_polling()


if __name__ == "__main__":
    main()
