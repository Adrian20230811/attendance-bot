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

def create_main_keyboard():
    """创建主功能键盘"""
    keyboard = [
        ['📊 开始上班', '😴 开始休息'],
        ['💼 结束休息', '🏁 下班打卡'],
        ['📈 当前状态', '🆘 帮助']
    ]
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="请选择操作或输入命令"
    )

async def start(update: Update, context: CallbackContext):
    welcome_text = (
        "👋 欢迎使用考勤机器人！\n\n"
        "📌 您可以使用以下按钮或命令：\n"
        "• 📊 开始上班 - 上班打卡\n"
        "• 😴 开始休息 - 开始休息\n" 
        "• 💼 结束休息 - 结束休息\n"
        "• 🏁 下班打卡 - 下班并生成报告\n"
        "• 📈 当前状态 - 查看当前状态\n"
        "• 🆘 帮助 - 显示此帮助信息\n\n"
        "💡 提示：点击下方按钮快速操作！"
    )
    await update.message.reply_text(welcome_text, reply_markup=create_main_keyboard())

async def startwork(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id in data and data[user_id].get("status") == "working":
        t = datetime.datetime.fromtimestamp(data[user_id]["start"])
        await update.message.reply_text(f"⚠️ 你已于 {t.strftime('%H:%M:%S')} 开始上班", reply_markup=create_main_keyboard())
        return

    data[user_id] = {
        "start": now().timestamp(),
        "breaks": [],
        "status": "working"
    }
    save_data(data)

    await update.message.reply_text(
        f"✅ 上班打卡成功！\n时间：{now().strftime('%H:%M:%S')}",
        reply_markup=create_main_keyboard()
    )

async def break_start(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 请先开始上班", reply_markup=create_main_keyboard())
        return

    if data[user_id]["status"] == "break":
        await update.message.reply_text("😴 你已经在休息中", reply_markup=create_main_keyboard())
        return

    data[user_id]["breaks"].append({"start": now().timestamp(), "end": None})
    data[user_id]["status"] = "break"
    save_data(data)

    await update.message.reply_text("😴 已开始休息", reply_markup=create_main_keyboard())

async def break_end(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 请先开始上班", reply_markup=create_main_keyboard())
        return

    if data[user_id]["status"] == "working":
        await update.message.reply_text("💼 你并未处于休息状态", reply_markup=create_main_keyboard())
        return

    for b in data[user_id]["breaks"]:
        if b["end"] is None:
            b["end"] = now().timestamp()
            break

    data[user_id]["status"] = "working"
    save_data(data)

    await update.message.reply_text("💼 休息结束，继续工作!", reply_markup=create_main_keyboard())

async def endwork(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 你还未开始上班", reply_markup=create_main_keyboard())
        return

    user_data = data[user_id]
    start_time = user_data["start"]
    end_time = now().timestamp()

    # 自动结束休息
    if user_data["status"] == "break":
        for b in user_data["breaks"]:
            if b["end"] is None:
                b["end"] = end_time
                break

    total = end_time - start_time
    break_time = sum((b["end"] - b["start"]) for b in user_data["breaks"])
    work_time = total - break_time

    report = (
        "📋 **今日工作总结**\n\n"
        f"🕐 上班：{datetime.datetime.fromtimestamp(start_time).strftime('%H:%M:%S')}\n"
        f"🕔 下班：{datetime.datetime.fromtimestamp(end_time).strftime('%H:%M:%S')}\n\n"
        f"⏱️ 总时间：{seconds_to_hms(int(total))}\n"
        f"😴 休息：{seconds_to_hms(int(break_time))}\n"
        f"💼 实际工作：{seconds_to_hms(int(work_time))}\n\n"
        f"🎉 辛苦啦！"
    )

    del data[user_id]
    save_data(data)

    await update.message.reply_text(report, reply_markup=create_main_keyboard())

async def status(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("📊 未上班，请先开始上班", reply_markup=create_main_keyboard())
        return

    d = data[user_id]
    stat = "💼 工作中" if d["status"] == "working" else "😴 休息中"
    breaks_count = len([b for b in d["breaks"] if b["end"] is not None])

    await update.message.reply_text(
        f"📊 当前状态：{stat}\n"
        f"🕐 上班时间：{datetime.datetime.fromtimestamp(d['start']).strftime('%H:%M:%S')}\n"
        f"📅 日期：{datetime.datetime.fromtimestamp(d['start']).strftime('%Y-%m-%d')}\n"
        f"😴 休息次数：{breaks_count}次",
        reply_markup=create_main_keyboard()
    )

async def handle_button_press(update: Update, context: CallbackContext):
    """处理按钮点击事件"""
    text = update.message.text
    
    if "开始上班" in text:
        await startwork(update, context)
    elif "开始休息" in text:
        await break_start(update, context)
    elif "结束休息" in text:
        await break_end(update, context)
    elif "下班打卡" in text:
        await endwork(update, context)
    elif "当前状态" in text:
        await status(update, context)
    elif "帮助" in text:
        await start(update, context)
    else:
        await update.message.reply_text(
            "❓ 未知命令，请使用下方按钮或输入 /start 查看帮助",
            reply_markup=create_main_keyboard()
        )

async def close_keyboard(update: Update, context: CallbackContext):
    """关闭键盘"""
    await update.message.reply_text(
        "⌨️ 键盘已关闭，发送 /start 重新打开",
        reply_markup=ReplyKeyboardRemove()
    )

def main():
    try:
        token = get_token()
        
        # 使用现代版本
        application = Application.builder().token(token).build()

        # 添加命令处理器
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("startwork", startwork))
        application.add_handler(CommandHandler("break", break_start))
        application.add_handler(CommandHandler("resume", break_end))
        application.add_handler(CommandHandler("endwork", endwork))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("close", close_keyboard))
        
        # 添加按钮消息处理器
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))

        logger.info("🚀 机器人启动成功！")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ 机器人启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
