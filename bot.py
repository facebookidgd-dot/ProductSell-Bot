import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiohttp import web
import firebase_admin
from firebase_admin import credentials, firestore

# --- Configuration ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- Firebase Setup ---
cred = credentials.Certificate(os.getenv('FIREBASE_SERVICE_ACCOUNT'))
firebase_admin.initialize_app(cred)
db = firestore.client()

# --- States for Admin ---
class AdminStates(StatesGroup):
    set_welcome = State()
    add_cat_name = State()
    add_prod_name = State()
    add_prod_price = State()
    add_prod_cat_id = State()
    add_prod_content = State()

# --- Auto-Initialization Logic ---
async def initialize_database():
    """বট চালু হওয়ার সময় চেক করবে ডাটাবেস ঠিক আছে কি না"""
    print("⚙️ Initializing Database...")
    # ওয়েলকাম মেসেজ চেক এবং অটো-ক্রিয়েট
    doc_ref = db.collection('settings').document('welcome')
    doc = doc_ref.get()
    if not doc.exists:
        print("✨ Creating default welcome message...")
        doc_ref.set({'text': "👋 স্বাগতম! আমাদের ডিজিটাল শপে আপনাকে স্বাগতম।\nনিচের মেনু থেকে অপশন সিলেক্ট করুন:"})
    print("✅ Database Ready!")

# --- Keyboards ---
def user_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Products"), KeyboardButton(text="📦 My Orders")],
        [KeyboardButton(text="🎁 Referral"), KeyboardButton(text="💬 Support")]
    ], resize_keyboard=True)

def admin_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Add Category"), KeyboardButton(text="➕ Add Product")],
        [KeyboardButton(text="📝 Change Welcome"), KeyboardButton(text="📊 Stats")],
        [KeyboardButton(text="🔙 Back to User Menu")]
    ], resize_keyboard=True)

# --- Handlers: User Side ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # অটোমেটিক ওয়েলকাম মেসেজ ডাটাবেস থেকে নেওয়া
    doc = db.collection('settings').document('welcome').get()
    welcome_text = doc.to_dict()['text'] if doc.exists else "Welcome!"
    
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Admin Panel:", reply_markup=admin_main_menu())
    else:
        await message.answer(welcome_text, reply_markup=user_main_menu())

@dp.message(F.text == "🛒 Products")
async def show_categories(message: types.Message):
    # ক্যাটাগরি অটোমেটিক ডাটাবেস থেকে আসবে
    cats_ref = db.collection('categories').stream()
    buttons = []
    found = False
    for doc in cats_ref:
        found = True
        buttons.append([InlineKeyboardButton(text=doc.to_dict()['name'], callback_data=f"cat_{doc.id}")])
    
    if not found:
        await message.answer("দুঃখিত, বর্তমানে কোনো ক্যাটাগরি নেই।")
        return

    await message.answer("ক্যাটেগরি সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("cat_"))
async def show_products(callback_query: types.CallbackQuery):
    cat_id = callback_query.data.split("_")[1]
    prods_ref = db.collection('products').where("category_id", "==", cat_id).stream()
    
    buttons = []
    found = False
    for doc in prods_ref:
        found = True
        p = doc.to_dict()
        buttons.append([InlineKeyboardButton(text=f"{p['name']} - {p['price']}৳", callback_data=f"buy_{doc.id}")])
    
    if not found:
        await callback_query.answer("এই ক্যাটাগরিতে কোনো প্রোডাক্ট নেই!", show_alert=True)
    else:
        await callback_query.message.edit_text("প্রোডাক্ট সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# --- Handlers: Admin Side (Automatic Collection Creation) ---

@dp.message(F.text == "➕ Add Category")
async def admin_add_cat(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("নতুন ক্যাটাগরির নাম লিখুন:")
    await state.set_state(AdminStates.add_cat_name)

@dp.message(AdminStates.add_cat_name)
async def save_cat(message: types.Message, state: FSMContext):
    # ক্যাটাগরি সেভ করলেই Firebase অটোমেটিক 'categories' কালেকশন তৈরি করবে
    new_cat = db.collection('categories').add({'name': message.text})
    await message.answer(f"✅ ক্যাটাগরি '{message.text}' তৈরি হয়েছে!", reply_markup=admin_main_menu())
    await state.clear()

@dp.message(F.text == "➕ Add Product")
async def admin_add_prod(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("প্রোডাক্টের নাম লিখুন:")
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def proc_p_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("প্রোডাক্টের দাম লিখুন (শুধু সংখ্যা):")
    await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def proc_p_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("কোন ক্যাটাগরিতে যোগ করবেন? ক্যাটাগরির ID লিখুন (অথবা ক্যাটাগরি লিস্ট দেখতে 'List' লিখুন):")
    await state.set_state(AdminStates.add_prod_cat_id)

@dp.message(AdminStates.add_prod_cat_id)
async def proc_p_cat(message: types.Message, state: FSMContext):
    await state.update_data(cat_id=message.text)
    await message.answer("ডেলিভারি কন্টেন্ট (লিঙ্ক বা টেক্সট) লিখুন:")
    await state.set_state(AdminStates.add_prod_content)

@dp.message(AdminStates.add_prod_content)
async def proc_p_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # প্রোডাক্ট সেভ করলেই Firebase অটোমেটিক 'products' কালেকশন তৈরি করবে
    db.collection('products').add({
        'name': data['name'],
        'price': data['price'],
        'category_id': data['cat_id'],
        'content': message.text
    })
    await message.answer("✅ প্রোডাক্ট সফলভাবে যোগ হয়েছে!", reply_markup=admin_main_menu())
    await state.clear()

# --- Render Health Check (For 24/7) ---
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is Alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()

async def main():
    await initialize_database() # ডাটাবেস অটো-চেক
    await start_web_server()    # ২৪ ঘণ্টা অন রাখার জন্য
    print("🚀 Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
