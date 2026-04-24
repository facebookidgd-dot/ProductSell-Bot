import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# API Token (আপনার BotFather থেকে পাওয়া টোকেন দিন)
API_TOKEN = 'YOUR_BOT_TOKEN_HERE'
ADMIN_ID = 123456789  # আপনার Telegram ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- Keyboards ---
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🛒 Products", callback_data="view_products"),
        InlineKeyboardButton("📦 My Orders", callback_data="my_orders"),
        InlineKeyboardButton("🎁 Referral", callback_data="referral"),
        InlineKeyboardButton("💬 Support", callback_data="support")
    )
    return keyboard

# --- Handlers ---

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("👋 স্বাগতম! আমাদের ডিজিটাল শপে আপনাকে স্বাগতম।\nনিচের মেনু থেকে অপশন সিলেক্ট করুন:", reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data == 'view_products')
async def show_categories(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔐 VPN Services", callback_data="cat_vpn"))
    keyboard.add(InlineKeyboardButton("📱 Premium Apps", callback_data="cat_apps"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu"))
    await bot.edit_message_text("ক্যাটেগরি সিলেক্ট করুন:", callback_query.from_user.id, callback_query.message.text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'cat_vpn')
async def show_vpn_products(callback_query: types.CallbackQuery):
    # এখানে ডাটাবেস থেকে VPN প্রোডাক্ট আসবে
    text = "🔐 **Premium VPN Service**\n\n💰 Price: 100৳\n📝 30 Days Validity"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🛒 Buy Now", callback_data="buy_vpn_1"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="view_products"))
    await bot.edit_message_text(text, callback_query.from_user.id, callback_query.message.text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def payment_instruction(callback_query: types.CallbackQuery):
    instruction = (
        "💳 **Payment Instruction**\n\n"
        "Bkash/Nagad: `01XXXXXXXXX`\n"
        "Amount: 100৳\n\n"
        "✅ পেমেন্ট করার পর আপনার **Transaction ID** লিখে এখানে পাঠান।"
    )
    await bot.send_message(callback_query.from_user.id, instruction, parse_mode="Markdown")

# --- Admin Approval System (Concept) ---
# যখন ইউজার TRX ID পাঠাবে, অ্যাডমিনকে একটি বাটনসহ মেসেজ যাবে
async def notify_admin_new_order(user_id, product_name, price, trx_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{trx_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}_{trx_id}")
    )
    await bot.send_message(ADMIN_ID, f"🆕 **New Order!**\n\n👤 User: {user_id}\n📦 Product: {product_name}\n💰 Price: {price}\n🧾 TRX ID: {trx_id}", reply_markup=keyboard, parse_mode="Markdown")

if __name__ == '__main__':
    print("Bot is running...")
    executor.start_polling(dp, skip_updates=True)
