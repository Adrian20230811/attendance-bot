import json
import datetime
import os
import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 欢迎使用考勤机器人！\n\n"
        "📌 指令列表：\n"
        "/startwork - 开始上班\n"
        "/break - 开始休息\n"
        "/resume - 结束休息\n"
        "/endwork - 下班并生成报告\n"
        "/status - 查看当前状态"
    )

async def startwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id in data and data[user_id].get("status") == "working":
        t = datetime.datetime.fromtimestamp(data[user_id]["start"])
        return await update.message.reply_text(f"⚠️ 你已于 {t.strftime('%H:%M:%S')} 开始上班")

    data[user_id] = {
        "start": now().timestamp(),
        "breaks": [],
        "status": "working"
    }
    save_data(data)

    await update.message.reply_text(f"✅ 上班打卡成功！\n时间：{now().strftime('%H:%M:%S')}")

async def break_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        return await update.message.reply_text("❌ 请先 /startwork 上班")

    if data[user_id]["status"] == "break":
        return await update.message.reply_text("😴 你已经在休息中")

    data[user_id]["breaks"].append({"start": now().timestamp(), "end": None})
    data[user_id]["status"] = "break"
    save_data(data)

    await update.message.reply_text("😴 已开始休息")

async def break_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        return await update.message.reply_text("❌ 请先 /startwork 上班")

    if data[user_id]["status"] == "working":
        return await update.message.reply_text("💼 你并未处于休息状态")

    for b in data[user_id]["breaks"]:
        if b["end"] is None:
            b["end"] = now().timestamp()
            break

    data[user_id]["status"] = "working"
    save_data(data)

    await update.message.reply_text("💼 休息结束，继续工作!")

async def endwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        return await update.message.reply_text("❌ 你还未开始上班")

    user_data = data[user_id]
    start = user_data["start"]
    end = now().timestamp()

    # 自动结束休息
    if user_data["status"] == "break":
        for b in user_data["breaks"]:
            if b["end"] is None:
                b["end"] = end
                break

    total = end - start
    break_time = sum((b["end"] - b["start"]) for b in user_data["breaks"])
    work_time = total - break_time

    report = (
        "📋 **今日工作总结**\n\n"
        f"🕐 上班：{datetime.datetime.fromtimestamp(start).strftime('%H:%M:%S')}\n"
        f"🕔 下班：{datetime.datetime.fromtimestamp(end).strftime('%H:%M:%S')}\n\n"
        f"⏱️ 总时间：{seconds_to_hms(int(total))}\n"
        f"😴 休息：{seconds_to_hms(int(break_time))}\n"
        f"💼 实际工作：{seconds_to_hms(int(work_time))}\n\n"
        f"🎉 辛苦啦！"
    )

    del data[user_id]
    save_data(data)

    await update.message.reply_text(report)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        return await update.message.reply_text("📊 未上班，使用 /startwork 开始")

    d = data[user_id]
    stat = "💼 工作中" if d["status"] == "working" else "😴 休息中"

    await update.message.reply_text(
        f"📊 当前状态：{stat}\n"
        f"🕐 上班：{datetime.datetime.fromtimestamp(d['start']).strftime('%H:%M:%S')}"
    )

def main():
    try:
        token = get_token()
        
        # 关键修复：使用 Application.builder() 而不是 ApplicationBuilder()
        app = Application.builder().token(token).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("startwork", startwork))
        app.add_handler(CommandHandler("break", break_start))
        app.add_handler(CommandHandler("resume", break_end))
        app.add_handler(CommandHandler("endwork", endwork))
        app.add_handler(CommandHandler("status", status))

        logger.info("🚀 机器人启动成功！")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"❌ 机器人启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
