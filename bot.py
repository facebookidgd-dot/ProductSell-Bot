import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiohttp import web

# --- Configuration ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- States (FSM) ---
class AdminStates(StatesGroup):
    adding_product_name = State()
    adding_product_price = State()
    adding_product_desc = State()
    adding_product_content = State()
    broadcasting = State()

class UserStates(StatesGroup):
    submitting_trx = State()

# --- Keyboards (Reply Menu) ---

def user_main_menu():
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Products"), KeyboardButton(text="📦 My Orders")],
        [KeyboardButton(text="🎁 Referral"), KeyboardButton(text="💬 Support")],
        [KeyboardButton(text="ℹ️ Help")]
    ], resize_keyboard=True)
    return keyboard

def admin_main_menu():
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Add Product"), KeyboardButton(text="📊 Stats")],
        [KeyboardButton(text="📋 All Orders"), KeyboardButton(text="📢 Broadcast")],
        [KeyboardButton(text="👥 Users"), KeyboardButton(text="🔙 Back to User Menu")]
    ], resize_keyboard=True)
    return keyboard

# --- Handlers: User Side ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Welcome Admin! Select an option:", reply_markup=admin_main_menu())
    else:
        await message.answer("👋 Welcome to Digital Shop! Select a category:", reply_markup=user_main_menu())

@dp.message(F.text == "🛒 Products")
async def show_products(message: types.Message):
    # এখানে ডাটাবেস থেকে ক্যাটাগরি আসবে
    text = "Choose a category:\n🔐 VPN\n📱 Apps\n📚 Ebook"
    # ক্যাটাগরির জন্য ইনলাইন বাটন ব্যবহার করা ভালো UX এর জন্য
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 VPN Services", callback_data="cat_vpn")],
        [InlineKeyboardButton(text="📱 Premium Apps", callback_data="cat_apps")],
        [InlineKeyboardButton(text="📚 Ebooks", callback_data="cat_ebook")]
    ])
    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text == "🎁 Referral")
async def show_referral(message: types.Message):
    ref_link = f"https://t.me/YourBotUsername?start={message.from_user.id}"
    await message.answer(f"🔗 Your Referral Link:\n{ref_link}\n\nEarn rewards for every friend!")

@dp.message(F.text == "💬 Support")
async def show_support(message: types.Message):
    await message.answer("Contact Support: @YourAdminUsername")

@dp.message(F.text == "ℹ️ Help")
async def show_help(message: types.Message):
    await message.answer("How to use:\n1. Select Product\n2. Pay via Bkash/Nagad\n3. Submit TRX ID\n4. Get instant delivery!")

# --- Handlers: Admin Side ---

@dp.message(F.text == "🔙 Back to User Menu")
async def back_to_user(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Switching to User View...", reply_markup=user_main_menu())

@dp.message(F.text == "➕ Add Product")
async def add_prod_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Enter Product Name:")
    await state.set_state(AdminStates.adding_product_name)

@dp.message(AdminStates.adding_product_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Enter Product Price (e.g., 100):")
    await state.set_state(AdminStates.adding_product_price)

@dp.message(AdminStates.adding_product_price)
async def process_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Enter Product Description:")
    await state.set_state(AdminStates.adding_product_desc)

@dp.message(AdminStates.adding_product_desc)
async def process_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Enter Delivery Content (Link/Text/File ID):")
    await state.set_state(AdminStates.adding_product_content)

@dp.message(AdminStates.adding_product_content)
async def process_content(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    # এখানে ডাটাবেস (Firebase) এ সেভ করার কোড বসবে
    await message.answer(
        f"✅ Product Added Successfully!\n\n"
        f"📦 Name: {user_data['name']}\n"
        f"💰 Price: {user_data['price']}৳\n"
        f"📝 Desc: {user_data['desc']}",
        reply_markup=admin_main_menu()
    )
    await state.clear()

# --- Health Check for Render ---
async def handle_health_check(request):
    return web.Response(text="Bot is Online!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()

async def main():
    await start_web_server()
    print("🚀 Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    if not API_TOKEN:
        print("❌ ERROR: BOT_TOKEN missing!")
    else:
        asyncio.run(main())
