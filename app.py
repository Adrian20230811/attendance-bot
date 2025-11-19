import json
import datetime
import os
import logging
import sys
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

DATA_FILE = "attendance_data.json"

def load_data():
    try:
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存数据失败: {e}")

def get_token():
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("❌ 未找到 TOKEN 环境变量，请先设置 TOKEN")
    logger.info("✅ Token 已加载")
    return token

def now():
    return datetime.datetime.now()

def seconds_to_hms(sec):
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}小时 {m}分 {s}秒"

def create_simple_keyboard():
    """创建最简单的键盘测试"""
    keyboard = [
        ['上班', '休息'],
        ['状态', '帮助']
    ]
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True,
        one_time_keyboard=False
    )

async def start(update: Update, context: CallbackContext):
    """测试命令 - 只发送键盘"""
    await update.message.reply_text(
        "请点击下方按钮：",
        reply_markup=create_simple_keyboard()
    )

async def handle_buttons(update: Update, context: CallbackContext):
    """处理按钮点击"""
    text = update.message.text
    await update.message.reply_text(f"你点击了: {text}")

def main():
    try:
        token = get_token()
        application = Application.builder().token(token).build()

        # 只添加最简单的处理器
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

        logger.info("🚀 测试版机器人启动成功！")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ 机器人启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
