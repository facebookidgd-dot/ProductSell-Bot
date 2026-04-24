import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import time
import threading
from flask import Flask # Koyeb-এর জন্য প্রয়োজন

# --- Koyeb Web Server Setup ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    # Koyeb সাধারণত ৮০৮০ পোর্ট ব্যবহার করে
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Bot Setup ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
FIREBASE_JSON_STR = os.environ.get("FIREBASE_JSON")

if not all([BOT_TOKEN, ADMIN_ID, FIREBASE_JSON_STR]):
    raise ValueError("⚠️ Environment Variables missing! Check BOT_TOKEN, ADMIN_ID, or FIREBASE_JSON.")

bot = telebot.TeleBot(BOT_TOKEN)

# 🧱 Firebase Setup
try:
    firebase_credentials = json.loads(FIREBASE_JSON_STR)
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Connected Successfully!")
except Exception as e:
    print(f"❌ Firebase Connection Failed: {e}")

# 🔹 1. Start & Menu Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.chat.id)
    user_ref = db.collection('users').document(user_id)
    if not user_ref.get().exists:
        user_ref.set({
            'first_name': message.from_user.first_name,
            'username': message.from_user.username,
            'balance': 0,
            'joined_at': firestore.SERVER_TIMESTAMP
        })
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton('🛒 Products'), KeyboardButton('📦 My Orders'), KeyboardButton('💬 Support'), KeyboardButton('ℹ️ Help'))
    bot.send_message(message.chat.id, f"👋 স্বাগতম {message.from_user.first_name}!", reply_markup=markup)

# 🔹 2. Product Menu
@bot.message_handler(func=lambda message: message.text == '🛒 Products')
def show_products(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛒 Buy Now (100৳)", callback_data="buy_PremiumVPN_100"))
    product_text = "📦 *Premium VPN (1 Month)*\n\n💰 Price: 100৳"
    bot.send_message(message.chat.id, product_text, parse_mode='Markdown', reply_markup=markup)

# 🔹 3. Buy & TRX
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def process_buy(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    product_name, price = parts[1], parts[2]
    text = f"💳 *পেমেন্ট ইনস্ট্রাকশন:*\n\n💰 Amount: {price}৳\n\n📌 TRX ID লিখে পাঠান:"
    msg = bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    bot.register_next_step_handler(msg, receive_trx, product_name, price)

def receive_trx(message, product_name, price):
    trx_id = message.text
    user_id = str(message.chat.id)
    order_data = {'user_id': user_id, 'product_name': product_name, 'price': price, 'trx_id': trx_id, 'status': 'Pending', 'timestamp': firestore.SERVER_TIMESTAMP}
    update_time, order_ref = db.collection('orders').add(order_data)
    order_id = order_ref.id
    bot.send_message(user_id, "👉 ⏳ যাচাই হচ্ছে...")
    admin_text = f"🆕 *New Order!*\n👤 ID: `{user_id}`\n📦 {product_name}\n💰 {price}৳\n🧾 TRX: `{trx_id}`"
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}"))
    bot.send_message(ADMIN_ID, admin_text, parse_mode='Markdown', reply_markup=admin_markup)

# ⚡ 4. Admin Action
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('reject_'))
def admin_action(call):
    action, order_id = call.data.split('_')
    order_ref = db.collection('orders').document(order_id)
    order = order_ref.get()
    if not order.exists: return
    order_data = order.to_dict()
    user_id = order_data['user_id']
    if action == 'approve':
        order_ref.update({'status': 'Delivered'})
        bot.edit_message_text("✅ Approved!", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, "✅ পেমেন্ট সফল হয়েছে!")
    else:
        order_ref.update({'status': 'Rejected'})
        bot.edit_message_text("❌ Rejected!", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, "❌ পেমেন্ট রিজেক্ট হয়েছে।")

# --- Main Execution ---
if __name__ == "__main__":
    # Flask সার্ভারটি ব্যাকগ্রাউন্ডে চালু হবে (Koyeb এর জন্য)
    threading.Thread(target=run_flask, daemon=True).start()
    
    bot.remove_webhook()
    print("⏳ Waiting for stability...")
    time.sleep(10)
    print("🚀 Bot is Starting Now...")
    bot.infinity_polling()
