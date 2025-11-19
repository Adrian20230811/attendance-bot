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
    """加载考勤数据"""
    try:
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data):
    """保存考勤数据"""
    try:
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存数据失败: {e}")

def get_token():
    """获取机器人Token"""
    token = os.getenv("TOKEN")
    if not token:
        logger.error("❌ 未找到 TOKEN 环境变量")
        raise ValueError("❌ 未找到 TOKEN 环境变量，请在 Railway Variables 中设置 TOKEN")
    logger.info("✅ Token 验证通过")
    return token

def now():
    """获取当前时间"""
    return datetime.datetime.now()

def seconds_to_hms(seconds):
    """秒数转换为时分秒格式"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}小时{minutes}分{seconds}秒"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令 - 显示欢迎信息和指令列表"""
    welcome_text = """
👋 欢迎使用考勤机器人！

📋 **指令列表：**
/startwork - 开始上班打卡
/break - 开始休息
/resume - 结束休息  
/status - 查看当前状态
/endwork - 下班并生成报告

💡 **使用流程：**
1. 使用 /startwork 开始上班
2. 休息时用 /break，回来时用 /resume
3. 下班时用 /endwork 生成报告

祝您工作愉快！💼
    """
    await update.message.reply_text(welcome_text)

async def startwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始上班打卡"""
    user_id = str(update.effective_user.id)
    data = load_data()

    # 检查是否已经上班
    if user_id in data and data[user_id].get("status") == "working":
        start_time = datetime.datetime.fromtimestamp(data[user_id]["start"])
        await update.message.reply_text(
            f"⚠️ 您已经在 {start_time.strftime('%H:%M:%S')} 开始上班了！"
        )
        return

    # 记录上班时间
    data[user_id] = {
        "start": now().timestamp(),
        "breaks": [],
        "status": "working"
    }
    save_data(data)

    current_time = now().strftime("%H:%M:%S")
    await update.message.reply_text(
        f"✅ **上班打卡成功！**\n\n"
        f"🕐 时间：{current_time}\n"
        f"💪 祝您工作顺利！"
    )

async def break_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始休息"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 请先使用 /startwork 开始上班")
        return

    if data[user_id]["status"] == "break":
        await update.message.reply_text("😴 您已经在休息中了")
        return

    # 记录休息开始时间
    data[user_id]["breaks"].append({
        "start": now().timestamp(), 
        "end": None
    })
    data[user_id]["status"] = "break"
    save_data(data)

    await update.message.reply_text("😴 **休息开始**\n\n好好休息一下～")

async def break_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """结束休息"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 请先使用 /startwork 开始上班")
        return

    if data[user_id]["status"] == "working":
        await update.message.reply_text("💼 您当前不在休息状态")
        return

    # 结束休息
    for break_session in data[user_id]["breaks"]:
        if break_session["end"] is None:
            break_session["end"] = now().timestamp()
            break

    data[user_id]["status"] = "working"
    save_data(data)

    await update.message.reply_text("💼 **休息结束**\n\n欢迎回来，继续工作！")

async def endwork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """结束工作并生成报告"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("❌ 您今天还没有上班记录")
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
    total_seconds = end_time - start_time
    break_seconds = sum(
        (b["end"] - b["start"]) for b in user_data["breaks"]
    )
    work_seconds = total_seconds - break_seconds

    # 生成报告
    report = f"""
📋 **今日工作总结**

🕐 上班时间：{datetime.datetime.fromtimestamp(start_time).strftime('%H:%M:%S')}
🕔 下班时间：{datetime.datetime.fromtimestamp(end_time).strftime('%H:%M:%S')}

⏱️ 总在岗时长：{seconds_to_hms(int(total_seconds))}
😴 休息时长：{seconds_to_hms(int(break_seconds))}
💼 实际工作时长：{seconds_to_hms(int(work_seconds))}

🎉 辛苦了一天，好好休息吧！
    """

    # 清除数据并保存
    del data[user_id]
    save_data(data)

    await update.message.reply_text(report)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看当前状态"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text(
            "📊 **当前状态：未上班**\n\n"
            "使用 /startwork 开始上班打卡"
        )
        return

    user_data = data[user_id]
    status_text = "💼 工作中" if user_data["status"] == "working" else "😴 休息中"
    start_time = datetime.datetime.fromtimestamp(user_data["start"]).strftime('%H:%M:%S')
    
    message = f"""
📊 **当前状态**

{status_text}
🕐 上班时间：{start_time}

💡 提示：{"使用 /break 开始休息" if user_data['status'] == 'working' else "使用 /resume 结束休息"}
    """
    
    await update.message.reply_text(message)

def main():
    """主函数"""
    try:
        # 获取Token并创建应用
        token = get_token()
        application = Application.builder().token(token).build()

        # 注册命令处理器
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("startwork", startwork))
        application.add_handler(CommandHandler("break", break_start))
        application.add_handler(CommandHandler("resume", break_end))
        application.add_handler(CommandHandler("endwork", endwork))
        application.add_handler(CommandHandler("status", status))

        # 启动机器人
        logger.info("🚀 考勤机器人启动成功！")
        logger.info("📱 机器人正在运行，等待用户命令...")
        application.run_polling()

    except Exception as e:
        logger.error(f"❌ 机器人启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
