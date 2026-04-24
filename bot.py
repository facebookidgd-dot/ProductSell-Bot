import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- Configuration ---
# Render Environment থেকে ভেরিয়েবল নিবে, না থাকলে এরর দিবে
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO)

# বট এবং ডিসপ্যাচার সেটআপ (Aiogram v3 style)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- Keyboards ---
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Products", callback_data="view_products")],
        [InlineKeyboardButton(text="📦 My Orders", callback_data="my_orders"), 
         InlineKeyboardButton(text="🎁 Referral", callback_data="referral")],
        [InlineKeyboardButton(text="💬 Support", callback_data="support"),
         InlineKeyboardButton(text="ℹ️ Help", callback_data="help")]
    ])
    return keyboard

# --- Handlers ---

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "👋 স্বাগতম! আমাদের ডিজিটাল শপে আপনাকে স্বাগতম।\nনিচের মেনু থেকে অপশন সিলেক্ট করুন:", 
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "view_products")
async def show_categories(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 VPN Services", callback_data="cat_vpn")],
        [InlineKeyboardButton(text="📱 Premium Apps", callback_data="cat_apps")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="main_menu")]
    ])
    await callback_query.message.edit_text("ক্যাটেগরি সিলেক্ট করুন:", reply_markup=keyboard)

@dp.callback_query(F.data == "cat_vpn")
async def show_vpn_products(callback_query: types.CallbackQuery):
    text = "🔐 **Premium VPN Service**\n\n💰 Price: 100৳\n📝 30 Days Validity"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Buy Now", callback_data="buy_vpn_1")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="view_products")]
    ])
    await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_"))
async def payment_instruction(callback_query: types.CallbackQuery):
    instruction = (
        "💳 **Payment Instruction**\n\n"
        "Bkash/Nagad: `01XXXXXXXXX`\n"
        "Amount: 100৳\n\n"
        "✅ পেমেন্ট করার পর আপনার **Transaction ID** লিখে এখানে পাঠান।"
    )
    await callback_query.message.answer(instruction, parse_mode="Markdown")
    await callback_query.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("নিচের মেনু থেকে অপশন সিলেক্ট করুন:", reply_markup=main_menu())

# --- Render Health Check Server (খুবই গুরুত্বপূর্ণ) ---
async def handle_health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render এর দেওয়া PORT ব্যবহার করবে
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Health check server started on port {port}")

# --- Main Function ---
async def main():
    # ১. প্রথমে ওয়েব সার্ভার চালু হবে (Render এর জন্য)
    await start_web_server()
    
    # ২. তারপর টেলিগ্রাম বট চালু হবে
    print("🚀 Starting Telegram Bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not API_TOKEN:
        print("❌ ERROR: BOT_TOKEN is not set in Environment Variables!")
    else:
        try:
            asyncio.run(main())
        except (KeyboardInterrupt, SystemExit):
            print("🛑 Bot stopped.")
