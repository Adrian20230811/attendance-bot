import os
import logging
import sys
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def debug_start(update: Update, context: CallbackContext):
    """调试命令，测试各种键盘类型"""
    user = update.effective_user
    
    # 测试1: 简单键盘
    keyboard1 = ReplyKeyboardMarkup([['按钮1', '按钮2']], resize_keyboard=True)
    await update.message.reply_text("测试1 - 简单键盘:", reply_markup=keyboard1)
    
    # 测试2: 多行键盘
    keyboard2 = ReplyKeyboardMarkup([
        ['第一行按钮1', '第一行按钮2'],
        ['第二行按钮']
    ], resize_keyboard=True)
    await update.message.reply_text("测试2 - 多行键盘:", reply_markup=keyboard2)
    
    # 测试3: 带占位符的键盘
    keyboard3 = ReplyKeyboardMarkup([
        ['📊 上班', '😴 休息'],
        ['📈 状态', '🆘 帮助']
    ], resize_keyboard=True, input_field_placeholder="请选择操作")
    await update.message.reply_text("测试3 - 带表情键盘:", reply_markup=keyboard3)
    
    logger.info(f"向用户 {user.id} 发送了键盘测试")

async def handle_message(update: Update, context: CallbackContext):
    """处理所有消息"""
    text = update.message.text
    user = update.effective_user
    logger.info(f"收到用户 {user.id} 的消息: {text}")
    await update.message.reply_text(f"收到: {text}")

async def check_version(update: Update, context: CallbackContext):
    """检查版本信息"""
    import telegram
    version_info = f"""
🤖 机器人诊断信息:

Python: {sys.version}
python-telegram-bot: {telegram.__version__}
    """
    await update.message.reply_text(version_info)

def main():
    try:
        token = os.getenv("TOKEN")
        if not token:
            logger.error("❌ 未找到 TOKEN 环境变量")
            return
        
        logger.info("✅ Token 已加载")
        
        application = Application.builder().token(token).build()
        
        # 添加处理器
        application.add_handler(CommandHandler("start", debug_start))
        application.add_handler(CommandHandler("version", check_version))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("🚀 诊断机器人启动成功！")
        logger.info("请发送 /start 进行测试")
        logger.info("请发送 /version 查看版本信息")
        
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ 机器人启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
