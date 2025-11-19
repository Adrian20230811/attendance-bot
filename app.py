import json
import datetime
import os
import logging
import sys
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
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

def seconds_to_hms(seconds):
    """将秒数转换为时分秒格式"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{int(hours)}小时{int(minutes)}分{int(seconds)}秒"

def create_main_keyboard():
    """创建主功能键盘 - 中文加英文"""
    keyboard = [
        ['📊 上班打卡 Check In', '🏁 下班打卡 Check Out'],
        ['😴 开始休息 Start Break', '💼 结束休息 End Break'],
        ['📈 今日统计 Today Stats', '📋 查看记录 View Records'],
        ['ℹ️ 帮助信息 Help', '❌ 关闭键盘 Close Keyboard']
    ]
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="请选择操作... Select an option..."
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 欢迎使用考勤机器人！Welcome to Attendance Bot!\n\n"
        "📌 可用命令 Available Commands：\n"
        "• /checkin - 上班打卡 Check in\n"
        "• /checkout - 下班打卡 Check out\n"
        "• /breakstart - 开始休息 Start break\n"
        "• /breakend - 结束休息 End break\n"
        "• /stats - 今日统计 Today stats\n"
        "• /records - 查看记录 View records\n\n"
        "💡 或者直接点击下方按钮操作！Or click the buttons below!"
    )
    await update.message.reply_text(welcome_text, reply_markup=create_main_keyboard())

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    now = datetime.datetime.now()

    data = load_data()
    data.setdefault(user_id, {
        "name": user.full_name, 
        "records": [], 
        "status": "off",
        "current_break_start": None
    })
    
    # 检查是否已经上班
    if data[user_id]["status"] == "working":
        await update.message.reply_text(
            "⚠️ 您已经上班打卡了！You have already checked in!",
            reply_markup=create_main_keyboard()
        )
        return
    
    data[user_id]["records"].append({
        "type": "checkin", 
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": now.timestamp()
    })
    data[user_id]["status"] = "working"
    data[user_id]["work_start"] = now.timestamp()
    save_data(data)

    await update.message.reply_text(
        f"✅ 上班打卡成功！Check in successful!\n时间 Time：{now.strftime('%H:%M:%S')}",
        reply_markup=create_main_keyboard()
    )

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    now = datetime.datetime.now()

    data = load_data()
    data.setdefault(user_id, {
        "name": user.full_name, 
        "records": [], 
        "status": "off",
        "current_break_start": None
    })
    
    # 检查是否已经下班
    if data[user_id]["status"] == "off":
        await update.message.reply_text(
            "⚠️ 您还没有上班打卡！You haven't checked in yet!",
            reply_markup=create_main_keyboard()
        )
        return
    
    # 如果正在休息，自动结束休息
    if data[user_id]["status"] == "break":
        break_end_time = now.timestamp()
        break_start_time = data[user_id]["current_break_start"]
        break_duration = break_end_time - break_start_time
        
        data[user_id]["records"].append({
            "type": "break_end", 
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": break_end_time,
            "break_duration": break_duration
        })
        data[user_id]["current_break_start"] = None
    
    # 计算总工作时间
    work_start_time = data[user_id].get("work_start")
    if work_start_time:
        total_work_time = now.timestamp() - work_start_time
        # 减去所有休息时间
        total_break_time = sum(record.get("break_duration", 0) for record in data[user_id]["records"] if record["type"] == "break_end")
        net_work_time = total_work_time - total_break_time
        
        data[user_id]["total_break_time"] = total_break_time
        data[user_id]["net_work_time"] = net_work_time
    
    data[user_id]["records"].append({
        "type": "checkout", 
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": now.timestamp()
    })
    data[user_id]["status"] = "off"
    save_data(data)

    # 生成报告
    report = await generate_daily_report(user_id, data[user_id])
    await update.message.reply_text(
        f"✅ 下班打卡成功！Check out successful!\n时间 Time：{now.strftime('%H:%M:%S')}\n\n{report}",
        reply_markup=create_main_keyboard()
    )

async def break_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    now = datetime.datetime.now()

    data = load_data()
    data.setdefault(user_id, {
        "name": user.full_name, 
        "records": [], 
        "status": "off",
        "current_break_start": None
    })
    
    # 检查是否在上班状态
    if data[user_id]["status"] != "working":
        await update.message.reply_text(
            "⚠️ 请先上班打卡才能开始休息！Please check in first to start break!",
            reply_markup=create_main_keyboard()
        )
        return
    
    # 检查是否已经在休息
    if data[user_id]["status"] == "break":
        await update.message.reply_text(
            "⚠️ 您已经在休息中！You are already on break!",
            reply_markup=create_main_keyboard()
        )
        return
    
    data[user_id]["records"].append({
        "type": "break_start", 
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": now.timestamp()
    })
    data[user_id]["status"] = "break"
    data[user_id]["current_break_start"] = now.timestamp()
    save_data(data)

    await update.message.reply_text(
        f"😴 开始休息！Break started!\n时间 Time：{now.strftime('%H:%M:%S')}",
        reply_markup=create_main_keyboard()
    )

async def break_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    now = datetime.datetime.now()

    data = load_data()
    data.setdefault(user_id, {
        "name": user.full_name, 
        "records": [], 
        "status": "off",
        "current_break_start": None
    })
    
    # 检查是否在休息状态
    if data[user_id]["status"] != "break":
        await update.message.reply_text(
            "⚠️ 您没有在休息中！You are not on break!",
            reply_markup=create_main_keyboard()
        )
        return
    
    break_end_time = now.timestamp()
    break_start_time = data[user_id]["current_break_start"]
    break_duration = break_end_time - break_start_time
    
    data[user_id]["records"].append({
        "type": "break_end", 
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": break_end_time,
        "break_duration": break_duration
    })
    data[user_id]["status"] = "working"
    data[user_id]["current_break_start"] = None
    save_data(data)

    await update.message.reply_text(
        f"💼 休息结束！Break ended!\n时间 Time：{now.strftime('%H:%M:%S')}\n"
        f"休息时长 Break duration: {seconds_to_hms(break_duration)}",
        reply_markup=create_main_keyboard()
    )

async def generate_daily_report(user_id, user_data):
    """生成每日工作报告"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_records = [r for r in user_data["records"] if r["time"].startswith(today)]
    
    if not today_records:
        return "📊 今日无记录 No records for today"
    
    # 计算统计信息
    total_break_time = user_data.get("total_break_time", 0)
    net_work_time = user_data.get("net_work_time", 0)
    total_work_time = user_data.get("net_work_time", 0) + total_break_time
    
    # 计算休息次数
    break_count = len([r for r in today_records if r["type"] == "break_start"])
    
    report = (
        f"📊 今日工作统计 Daily Work Statistics\n\n"
        f"⏱️ 总时长 Total: {seconds_to_hms(total_work_time)}\n"
        f"😴 休息时间 Break: {seconds_to_hms(total_break_time)}\n"
        f"💼 净工作时间 Work: {seconds_to_hms(net_work_time)}\n"
        f"📅 休息次数 Breaks: {break_count}次 times\n"
        f"📈 工作效率 Efficiency: {net_work_time/total_work_time*100:.1f}%"
    )
    
    return report

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示今日统计"""
    user = update.effective_user
    user_id = str(user.id)
    
    data = load_data()
    if user_id not in data:
        await update.message.reply_text(
            "📊 今日无记录 No records for today",
            reply_markup=create_main_keyboard()
        )
        return
    
    user_data = data[user_id]
    report = await generate_daily_report(user_id, user_data)
    await update.message.reply_text(report, reply_markup=create_main_keyboard())

async def show_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    data = load_data()
    if user_id not in data or not data[user_id]["records"]:
        await update.message.reply_text(
            "📊 暂无打卡记录 No records yet",
            reply_markup=create_main_keyboard()
        )
        return
    
    records = data[user_id]["records"]
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_records = [r for r in records if r["time"].startswith(today)]
    
    if not today_records:
        response = f"📅 {today}\n暂无今日打卡记录 No records for today"
    else:
        response = f"📅 {today} 打卡记录 Attendance Records：\n\n"
        for i, record in enumerate(today_records, 1):
            if record["type"] == "checkin":
                record_type = "🟢 上班 Check In"
            elif record["type"] == "checkout":
                record_type = "🔴 下班 Check Out"
            elif record["type"] == "break_start":
                record_type = "😴 开始休息 Break Start"
            elif record["type"] == "break_end":
                duration = record.get("break_duration", 0)
                record_type = f"💼 结束休息 Break End ({seconds_to_hms(duration)})"
            else:
                record_type = record["type"]
            
            time = record["time"][11:]  # 只取时间部分
            response += f"{i}. {record_type} - {time}\n"
        
        # 显示当前状态
        current_status = data[user_id]["status"]
        status_text = {
            "off": "🔴 已下班 Off duty",
            "working": "🟢 工作中 Working",
            "break": "😴 休息中 On break"
        }.get(current_status, "❓ 未知状态 Unknown")
        
        response += f"\n当前状态 Current Status: {status_text}"
    
    await update.message.reply_text(response, reply_markup=create_main_keyboard())

async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮点击事件"""
    text = update.message.text
    
    if "上班打卡" in text or "Check In" in text:
        await checkin(update, context)
    elif "下班打卡" in text or "Check Out" in text:
        await checkout(update, context)
    elif "开始休息" in text or "Start Break" in text:
        await break_start(update, context)
    elif "结束休息" in text or "End Break" in text:
        await break_end(update, context)
    elif "今日统计" in text or "Today Stats" in text:
        await show_stats(update, context)
    elif "查看记录" in text or "View Records" in text:
        await show_records(update, context)
    elif "帮助信息" in text or "Help" in text:
        await start(update, context)
    elif "关闭键盘" in text or "Close Keyboard" in text:
        await update.message.reply_text(
            "⌨️ 键盘已关闭，发送 /start 重新打开\nKeyboard closed, send /start to reopen",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text(
            "❓ 未知命令，请使用下方按钮或输入 /start 查看帮助\nUnknown command, please use the buttons below or type /start for help",
            reply_markup=create_main_keyboard()
        )

async def close_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """关闭键盘命令"""
    await update.message.reply_text(
        "⌨️ 键盘已关闭，发送 /start 重新打开\nKeyboard closed, send /start to reopen",
        reply_markup=ReplyKeyboardRemove()
    )

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ 没找到 TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    logger.info("✅ Token 已加载")
    application = Application.builder().token(token).build()

    # 注册命令处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("checkout", checkout))
    application.add_handler(CommandHandler("breakstart", break_start))
    application.add_handler(CommandHandler("breakend", break_end))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("records", show_records))
    application.add_handler(CommandHandler("close", close_keyboard))
    
    # 注册按钮消息处理器
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))

    logger.info("🚀 机器人启动成功！")
    application.run_polling()

if __name__ == "__main__":
    main()
