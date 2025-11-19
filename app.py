import json
import datetime
import os
import logging
from typing import Dict, List, Optional
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackContext, 
    ConversationHandler,
    MessageHandler,
    filters
)

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 常量定义
DATA_FILE = "attendance_data.json"
BACKUP_FILE = "attendance_backup.json"

# 对话状态
SETTING_REMINDER = 1

def load_data() -> Dict:
    """加载数据"""
    try:
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data: Dict) -> None:
    """保存数据并创建备份"""
    # 先备份当前数据
    try:
        existing_data = load_data()
        with open(BACKUP_FILE, "w", encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
    except:
        pass
    
    # 保存新数据
    with open(DATA_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user_name(update: Update) -> str:
    """获取用户显示名称"""
    user = update.effective_user
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    elif user.first_name:
        return user.first_name
    elif user.username:
        return f"@{user.username}"
    else:
        return f"用户{user.id}"

def format_timestamp(timestamp: float) -> str:
    """格式化时间戳"""
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

def seconds_to_hms(seconds: int) -> str:
    """秒数转换为时分秒"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}小时{m}分{s}秒"
    elif m > 0:
        return f"{m}分{s}秒"
    else:
        return f"{s}秒"

def calculate_daily_stats(user_data: Dict) -> Dict:
    """计算每日统计"""
    if "start" not in user_data:
        return {}
    
    start_time = user_data["start"]
    end_time = user_data.get("end", datetime.datetime.now().timestamp())
    
    total_work_seconds = end_time - start_time
    total_break_seconds = 0
    
    for break_session in user_data.get("breaks", []):
        break_end = break_session.get("end", datetime.datetime.now().timestamp())
        total_break_seconds += (break_end - break_session["start"])
    
    actual_work_seconds = total_work_seconds - total_break_seconds
    
    return {
        "total_work": int(total_work_seconds),
        "total_break": int(total_break_seconds),
        "actual_work": int(actual_work_seconds),
        "start_time": start_time,
        "end_time": end_time
    }

async def start(update: Update, context: CallbackContext) -> None:
    """开始命令"""
    user_name = get_user_name(update)
    
    welcome_text = f"""
👋 欢迎 {user_name} 使用考勤机器人！

📋 **可用命令：**
/startwork - 开始上班打卡
/break - 开始休息
/resume - 结束休息
/status - 查看当前状态
/endwork - 下班并生成报告
/stats - 查看今日统计
/settings - 设置提醒

💡 **使用流程：**
1. 使用 /startwork 开始上班
2. 休息时使用 /break，回来时用 /resume
3. 下班时使用 /endwork 生成报告

祝您工作愉快！💼
    """
    
    keyboard = [
        ["/startwork", "/status"],
        ["/break", "/resume"],
        ["/endwork", "/stats"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def startwork(update: Update, context: CallbackContext) -> None:
    """开始上班"""
    user_id = str(update.effective_user.id)
    user_name = get_user_name(update)
    data = load_data()
    
    # 检查是否已经上班
    if user_id in data and data[user_id].get("status") == "working":
        start_time = format_timestamp(data[user_id]["start"])
        await update.message.reply_text(
            f"⚠️ 您已经在 {start_time} 开始上班了！\n"
            f"使用 /status 查看当前状态"
        )
        return
    
    # 记录上班
    data[user_id] = {
        "name": user_name,
        "start": datetime.datetime.now().timestamp(),
        "breaks": [],
        "status": "working",
        "last_update": datetime.datetime.now().timestamp()
    }
    save_data(data)
    
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    await update.message.reply_text(
        f"✅ **上班打卡成功！**\n\n"
        f"👤 用户：{user_name}\n"
        f"🕐 时间：{current_time}\n"
        f"💪 祝您工作顺利！"
    )

async def break_start(update: Update, context: CallbackContext) -> None:
    """开始休息"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data or data[user_id].get("status") != "working":
        await update.message.reply_text(
            "❌ 请先使用 /startwork 开始上班后再休息。"
        )
        return
    
    # 记录休息开始
    data[user_id]["breaks"].append({
        "start": datetime.datetime.now().timestamp(),
        "end": None
    })
    data[user_id]["status"] = "break"
    data[user_id]["last_update"] = datetime.datetime.now().timestamp()
    save_data(data)
    
    await update.message.reply_text(
        "😴 **休息开始**\n\n"
        "好好休息一下～\n"
        "休息结束后记得使用 /resume 回来工作哦！"
    )

async def break_end(update: Update, context: CallbackContext) -> None:
    """结束休息"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data or data[user_id].get("status") != "break":
        await update.message.reply_text(
            "❌ 您当前不在休息状态。\n"
            "使用 /break 开始休息。"
        )
        return
    
    # 结束最近的休息
    for break_session in reversed(data[user_id]["breaks"]):
        if break_session["end"] is None:
            break_session["end"] = datetime.datetime.now().timestamp()
            break
    
    data[user_id]["status"] = "working"
    data[user_id]["last_update"] = datetime.datetime.now().timestamp()
    save_data(data)
    
    await update.message.reply_text(
        "💼 **休息结束**\n\n"
        "欢迎回来！继续努力工作吧！💪"
    )

async def status(update: Update, context: CallbackContext) -> None:
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
    stats = calculate_daily_stats(user_data)
    
    if user_data["status"] == "working":
        status_text = "💼 工作中"
        current_session = "上班"
        start_time = user_data["start"]
    else:
        status_text = "😴 休息中"
        current_session = "休息"
        # 找到最近的休息开始时间
        start_time = None
        for break_session in reversed(user_data["breaks"]):
            if break_session["end"] is None:
                start_time = break_session["start"]
                break
    
    status_message = f"""
📊 **当前状态**

{status_text}
👤 用户：{user_data.get('name', 'N/A')}
🕐 {current_session}开始：{format_timestamp(start_time)}
⏱️ 实际工作时长：{seconds_to_hms(stats['actual_work'])}

💡 提示：{"使用 /resume 结束休息" if user_data['status'] == 'break' else "使用 /break 开始休息"}
    """
    
    await update.message.reply_text(status_message)

async def stats(update: Update, context: CallbackContext) -> None:
    """查看今日统计"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data:
        await update.message.reply_text(
            "❌ 今天还没有上班记录。\n"
            "使用 /startwork 开始上班"
        )
        return
    
    user_data = data[user_id]
    stats = calculate_daily_stats(user_data)
    
    stats_message = f"""
📈 **今日工作统计**

👤 用户：{user_data.get('name', 'N/A')}
🟢 状态：{'工作中' if user_data['status'] == 'working' else '休息中'}
🕐 上班时间：{format_timestamp(stats['start_time'])}
⏱️ 总时长：{seconds_to_hms(stats['total_work'])}
😴 休息时长：{seconds_to_hms(stats['total_break'])}
💼 实际工作：{seconds_to_hms(stats['actual_work'])}

📊 工作效率：{stats['actual_work'] / stats['total_work'] * 100:.1f}%
    """
    
    await update.message.reply_text(stats_message)

async def endwork(update: Update, context: CallbackContext) -> None:
    """结束工作"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data:
        await update.message.reply_text(
            "❌ 今天还没有上班记录。\n"
            "使用 /startwork 开始上班"
        )
        return
    
    user_data = data[user_id]
    
    # 如果还在休息中，自动结束休息
    if user_data["status"] == "break":
        for break_session in reversed(user_data["breaks"]):
            if break_session["end"] is None:
                break_session["end"] = datetime.datetime.now().timestamp()
                break
    
    # 记录下班时间
    user_data["end"] = datetime.datetime.now().timestamp()
    user_data["status"] = "ended"
    user_data["last_update"] = datetime.datetime.now().timestamp()
    
    stats = calculate_daily_stats(user_data)
    
    # 生成报告
    report_message = f"""
📋 **今日工作总结**

👤 用户：{user_data.get('name', 'N/A')}
🕐 上班时间：{format_timestamp(stats['start_time'])}
🕔 下班时间：{format_timestamp(stats['end_time'])}
⏱️ 总在岗时长：{seconds_to_hms(stats['total_work'])}
😴 总休息时长：{seconds_to_hms(stats['total_break'])}
💼 实际工作时长：{seconds_to_hms(stats['actual_work'])}

📊 工作效率：{stats['actual_work'] / stats['total_work'] * 100:.1f}%

🎉 辛苦了一天，好好休息吧！
    """
    
    # 保存报告到用户数据
    user_data["daily_report"] = report_message
    save_data(data)
    
    # 发送报告并清除用户数据
    del data[user_id]
    save_data(data)
    
    await update.message.reply_text(report_message)

async def settings(update: Update, context: CallbackContext) -> None:
    """设置菜单"""
    settings_text = """
⚙️ **设置菜单**

目前支持的功能：
- 自动数据备份
- 工作状态提醒

更多功能开发中...

💡 建议：
- 下班前使用 /stats 查看统计
- 长时间休息记得使用 /break
    """
    
    await update.message.reply_text(settings_text)

async def error_handler(update: Update, context: CallbackContext) -> None:
    """错误处理"""
    logger.error(f"更新 {update} 导致错误: {context.error}")
    
    try:
        await update.message.reply_text(
            "❌ 发生了一个错误，请稍后重试。\n"
            "如果问题持续存在，请联系管理员。"
        )
    except:
        pass

def main():
    """主函数"""
    TOKEN = os.getenv("TOKEN")
    
    if not TOKEN:
        raise ValueError("❌ 未找到 TOKEN 环境变量")
    
    # 创建应用
    application = ApplicationBuilder().token(TOKEN).build()
    
    # 添加处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("startwork", startwork))
    application.add_handler(CommandHandler("break", break_start))
    application.add_handler(CommandHandler("resume", break_end))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("endwork", endwork))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("help", start))
    
    # 错误处理
    application.add_error_handler(error_handler)
    
    # 启动机器人
    logger.info("🤖 考勤机器人启动成功！")
    application.run_polling()

if __name__ == "__main__":
    main()
