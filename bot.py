import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import time
import threading
from flask import Flask

# --- REPLIT KEEP-ALIVE SERVER SETUP ---
# এটি Replit-কে বলবে যে বটটি সচল আছে, যাতে বটটি ঘুমিয়ে না যায়।
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is running and alive!"

def run_flask():
    # Replit সাধারণত ৮০৮০ পোর্ট ব্যবহার করে
    app.run(host='0.0.0.0', port=8080)

# --- BOT & DATABASE SETUP ---
# Replit-এর Secrets থেকে ভ্যারিয়েবল নিবে
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
FIREBASE_JSON_STR = os.environ.get("FIREBASE_JSON")

# Error Handling: যদি কোনো ভ্যারিয়েবল দিতে ভুলে যান
if not all([BOT_TOKEN, ADMIN_ID, FIREBASE_JSON_STR]):
    raise ValueError("⚠️ Environment Variables missing! Please check BOT_TOKEN, ADMIN_ID, or FIREBASE_JSON in Secrets.")

bot = telebot.TeleBot(BOT_TOKEN)

# Firebase Database Setup
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
    
    # Firebase-এ User Save করা
    user_ref = db.collection('users').document(user_id)
    if not user_ref.get().exists:
        user_ref.set({
            'first_name': message.from_user.first_name,
            'username': message.from_user.username,
            'balance': 0,
            'joined_at': firestore.SERVER_TIMESTAMP
        })

    # Keyboard Menu
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('🛒 Products'),
        KeyboardButton('📦 My Orders'),
        KeyboardButton('💬 Support'),
        KeyboardButton('ℹ️ Help')
    )
    bot.send_message(message.chat.id, f"👋 স্বাগতম {message.from_user.first_name}!\nআমাদের Digital Store-এ আপনাকে স্বাগতম। নিচে থেকে অপশন বেছে নিন:", reply_markup=markup)

# 🔹 2. Product Menu
@bot.message_handler(func=lambda message: message.text == '🛒 Products')
def show_products(message):
    markup = InlineKeyboardMarkup()
    btn_buy = InlineKeyboardButton("🛒 Buy Now (100৳)", callback_data="buy_PremiumVPN_100")
    markup.add(btn_buy)
    
    product_text = "📦 *Premium VPN (1 Month)*\n\n🔹 High Speed Connection\n🔹 No Logs\n💰 Price: 100৳"
    bot.send_message(message.chat.id, product_text, parse_mode='Markdown', reply_markup=markup)

# 🔹 3. Buy System & TRX Submission
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def process_buy(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    product_name = parts[1]
    price = parts[2]
    
    text = (
        "💳 *পেমেন্ট ইনস্ট্রাকশন:*\n\n"
        "🟢 Bkash/Nagad: `01XXXXXXXXX` (Personal)\n"
        f"💰 Amount: {price}৳\n\n"
        "📌 টাকা পাঠানোর পর আপনার *Transaction ID (TRX ID)* টি নিচে মেসেজ আকারে লিখে পাঠান:"
    )
    msg = bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    bot.register_next_step_handler(msg, receive_trx, product_name, price)

def receive_trx(message, product_name, price):
    trx_id = message.text
    user_id = str(message.chat.id)
    
    # Firebase-এ Order Save করা (Pending অবস্থায়)
    order_data = {
        'user_id': user_id,
        'product_name': product_name,
        'price': price,
        'trx_id': trx_id,
        'status': 'Pending',
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    
    update_time, order_ref = db.collection('orders').add(order_data)
    order_id = order_ref.id

    # ইউজারকে মেসেজ দেওয়া
    bot.send_message(user_id, "👉 ⏳ আপনার Payment যাচাই হচ্ছে… দয়া করে অপেক্ষা করুন।")

    # 📥 এডমিনকে মেসেজ পাঠানো
    admin_text = (
        f"🆕 *New Order Received!*\n\n"
        f"👤 User ID: `{user_id}`\n"
        f"📦 Product: {product_name}\n"
        f"💰 Price: {price}৳\n"
        f"🧾 TRX ID: `{trx_id}`"
    )
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}")
    )
    bot.send_message(ADMIN_ID, admin_text, parse_mode='Markdown', reply_markup=admin_markup)

# ⚡ 4. Admin Approve/Reject System
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('reject_'))
def admin_action(call):
    action, order_id = call.data.split('_')
    order_ref = db.collection('orders').document(order_id)
    order = order_ref.get()
    
    if not order.exists:
        bot.answer_callback_query(call.id, "Order not found!")
        return

    order_data = order.to_dict()
    user_id = order_data['user_id']
    product_name = order_data['product_name']

    if action == 'approve':
        order_ref.update({'status': 'Delivered'})
        bot.edit_message_text("✅ Order Approved!", call.message.chat.id, call.message.message_id)
        
        delivery_text = (
            f"✅ *Payment Confirmed!*\n\n"
            f"আপনার {product_name} এর ডিটেইলস নিচে দেওয়া হলো:\n"
            f"🔗 *Link:* https://example.com/download\n"
            f"🔑 *Code:* `1234-ABCD-5678`\n\n"
            f"ধন্যবাদ আমাদের সাথে থাকার জন্য!"
        )
        bot.send_message(user_id, delivery_text, parse_mode='Markdown')

    elif action == 'reject':
        order_ref.update({'status': 'Rejected'})
        bot.edit_message_text("❌ Order Rejected!", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, "❌ দুঃখিত! আপনার Payment টি যাচাই করা সম্ভব হয়নি। এডমিনের সাথে যোগাযোগ করুন।")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # ১. Flask সার্ভারটি একটি আলাদা থ্রেডে চালু করা হচ্ছে (Replit Keep-alive এর জন্য)
    threading.Thread(target=run_flask, daemon=True).start()
    
    # ২. আগের কোনো কানেকশন থাকলে তা রিমুভ করা
    bot.remove_webhook()
    print("⏳ Waiting for stability...")
    time.sleep(10)
    
    # ৩. বট পোলিং শুরু করা
    print("🚀 Bot is Starting Now...")
    bot.infinity_polling()
