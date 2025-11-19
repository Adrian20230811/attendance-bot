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
    """加载数据"""
    try:
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data):
    """保存数据"""
    try:
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存数据失败: {e}")

def get_token():
    """获取 Token"""
    token = os.getenv("TOKEN")
    
    if not token:
        logger.error("❌ 未找到 TOKEN 环境变量")
        raise ValueError("未找到 TOKEN 环境变量")
    
    logger.info("✅ Token 验证通过")
    return token

def now():
    return datetime.datetime.now()

def seconds_to_hms(seconds):
    """秒数转换为时分秒"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}小时 {m}分 {s}秒"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    await update.message.reply_text(
        "👋 欢迎使用考勤机器人！\n\n"
        "📋 **可用命令：**\n"
        "/startwork - 开始上班\n"
        "/break - 开始休息\n"
        "/resume - 结束休息\n"
        "/endwork - 下班并生成报告\n"
        "/status - 查看当前状态\n\n"
        "💡 使用 /startwork 开始记录您的工作时间！"
    )

async def startwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始上班"""
    user_id = str(update.effective_user.id)
    data = load_data()

    # 检查是否已经上班
    if user_id in data and data[user_id].get("status") == "working":
        start_time = datetime.datetime.fromtimestamp(data[user_id]["start"])
        await update.message.reply_text(
            f"⚠️ 您已经在 {start_time.strftime('%H:%M:%S')} 开始上班了！"
        )
        return

    data[user_id] = {
        "start": now().timestamp(),
        "breaks": [],
        "status": "working"
    }
    save_data(data)

    current_time = now().strftime("%H:%M:%S")
    await update.message.reply_text(
        f"✅ **上班打卡成功！**\n"
        f"🕐 时间: {current_time}\n"
        f"💪 祝您工作顺利！"
    )

async def break_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始休息"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 请先用 /startwork 开始上班。")
        return

    if data[user_id]["status"] == "break":
        await update.message.reply_text("😴 你已经在休息中。")
        return

    data[user_id]["breaks"].append({"start": now().timestamp(), "end": None})
    data[user_id]["status"] = "break"
    save_data(data)

    await update.message.reply_text("😴 已开始休息，好好放松一下！")

async def break_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """结束休息"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 请先用 /startwork 开始上班。")
        return

    if data[user_id]["status"] == "working":
        await update.message.reply_text("💼 你当前不在休息状态。")
        return

    # 结束最近的休息
    for break_session in data[user_id]["breaks"]:
        if break_session["end"] is None:
            break_session["end"] = now().timestamp()
            break

    data[user_id]["status"] = "working"
    save_data(data)

    await update.message.reply_text("💼 休息结束，继续工作！")

async def endwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """结束工作"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 请先用 /startwork 开始上班。")
        return

    user_data = data[user_id]
    start_time = user_data["start"]
    end_time = now().timestamp()

    # 如果还在休息中，自动结束休息
    if user_data["status"] == "break":
        for break_session in user_data["breaks"]:
            if break_session["end"] is None:
                break_session["end"] = end_time
                break

    # 计算工作时间
    total_work_seconds = end_time - start_time
    total_break_seconds = 0
    
    for break_session in user_data["breaks"]:
        break_end = break_session.get("end", end_time)
        total_break_seconds += (break_end - break_session["start"])

    actual_work_seconds = total_work_seconds - total_break_seconds

    # 生成报告
    report = (
        "📋 **今日工作总结**\n\n"
        f"🕐 上班时间: {datetime.datetime.fromtimestamp(start_time).strftime('%H:%M:%S')}\n"
        f"🕔 下班时间: {datetime.datetime.fromtimestamp(end_time).strftime('%H:%M:%S')}\n"
        f"⏱️ 总在岗时长: {seconds_to_hms(int(total_work_seconds))}\n"
        f"😴 休息时长: {seconds_to_hms(int(total_break_seconds))}\n"
        f"💼 实际工作: {seconds_to_hms(int(actual_work_seconds))}\n\n"
        f"🎉 辛苦了一天，好好休息吧！"
    )

    # 删除用户数据
    del data[user_id]
    save_data(data)

    await update.message.reply_text(report)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看状态"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("📊 状态: 未上班\n使用 /startwork 开始上班")
        return

    user_data = data[user_id]
    status_text = "💼 工作中" if user_data["status"] == "working" else "😴 休息中"
    start_time = datetime.datetime.fromtimestamp(user_data["start"]).strftime('%H:%M:%S')
    
    await update.message.reply_text(
        f"📊 **当前状态**\n\n"
        f"{status_text}\n"
        f"🕐 上班时间: {start_time}\n"
        f"💡 提示: {'使用 /break 开始休息' if user_data['status'] == 'working' else '使用 /resume 结束休息'}"
    )

def main():
    """主函数"""
    try:
        # 获取 Token
        token = get_token()
        
        logger.info("🚀 正在启动考勤机器人...")
        
        # 创建 Application - 这是关键修复
        application = Application.builder().token(token).build()

        # 添加命令处理器
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("startwork", startwork))
        application.add_handler(CommandHandler("break", break_start))
        application.add_handler(CommandHandler("resume", break_end))
        application.add_handler(CommandHandler("endwork", endwork))
        application.add_handler(CommandHandler("status", status))

        logger.info("✅ 机器人启动成功，开始轮询...")
        
        # 启动轮询
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ 机器人启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
