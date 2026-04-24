import telebot
import os
from flask import Flask
import threading

# Flask for Replit/Render keep-alive
app = Flask(__name__)

@app.route('/')
def home(): 
    return "Bot is Alive!"

def run_flask(): 
    app.run(host='0.0.0.0', port=8080)

# BOT SETUP
# Render-এর Environment Variables থেকে টোকেনটি নিবে
BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✅ অভিনন্দন! আপনার বট এখন কাজ করছে।")

if __name__ == "__main__":
    # Flask সার্ভারটি ব্যাকগ্রাউন্ডে চলবে
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Testing bot... Send /start in Telegram!")
    # বটটি চালু থাকবে
    bot.infinity_polling()
