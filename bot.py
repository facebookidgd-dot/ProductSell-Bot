 import telebot
import os
from flask import Flask
import threading

# Flask for Replit keep-alive
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# BOT SETUP
BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ অভিনন্দন! আপনার বট এখন কাজ করছে।")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Testing bot... Send /start in Telegram!")
    bot.infinity_polling()
