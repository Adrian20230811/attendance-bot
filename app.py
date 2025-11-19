import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext

async def minimal_test(update: Update, context: CallbackContext):
    keyboard = ReplyKeyboardMarkup([['测试按钮']], resize_keyboard=True)
    await update.message.reply_text("最小测试:", reply_markup=keyboard)

def main():
    application = Application.builder().token(os.getenv("TOKEN")).build()
    application.add_handler(CommandHandler("test", minimal_test))
    application.run_polling()

if __name__ == "__main__":
    main()
