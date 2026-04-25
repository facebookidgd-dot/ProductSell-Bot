import os
import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiohttp import web
import firebase_admin
from firebase_admin import credentials, firestore

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO)

# Environment Variables (Render এ অবশ্যই সেট করবেন)
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# --- Firebase Initialization (Handles JSON String directly) ---
try:
    service_account_info = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase Connected Successfully!")
except Exception as e:
    print(f"❌ Firebase Connection Error: {e}")
    exit(1)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- FSM States ---
class AdminStates(StatesGroup):
    set_welcome = State()
    add_cat_name = State()
    add_prod_name = State()
    add_prod_price = State()
    add_prod_cat_id = State()
    add_prod_content = State()
    broadcast = State()

class UserStates(StatesGroup):
    submitting_trx = State()

# --- Keyboards ---

def user_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Products"), KeyboardButton(text="📦 My Orders")],
        [KeyboardButton(text="🎁 Referral"), KeyboardButton(text="💬 Support")]
    ], resize_keyboard=True)

def admin_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Add Category"), KeyboardButton(text="➕ Add Product")],
        [KeyboardButton(text="📝 Change Welcome"), KeyboardButton(text="📢 Broadcast")],
        [KeyboardButton(text="🔙 Back to User Menu")]
    ], resize_keyboard=True)

# --- Database Initialization (Auto-creation) ---
async def initialize_db():
    print("⚙️ Initializing Database...")
    doc_ref = db.collection('settings').document('welcome')
    doc = doc_ref.get()
    if not doc.exists:
        doc_ref.set({'text': "👋 স্বাগতম! আমাদের ডিজিটাল শপে আপনাকে স্বাগতম।\nনিচের মেনু থেকে অপশন সিলেক্ট করুন:"})
    print("✅ Database Ready!")

# --- Handlers: User Side ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    doc = db.collection('settings').document('welcome').get()
    welcome_text = doc.to_dict()['text'] if doc.exists else "Welcome!"
    
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Welcome Admin!", reply_markup=admin_main_menu())
    else:
        await message.answer(welcome_text, reply_markup=user_main_menu())

@dp.message(F.text == "🛒 Products")
async def show_categories(message: types.Message):
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
async def show_products_in_cat(callback_query: types.CallbackQuery):
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

@dp.callback_query(F.data.startswith("buy_"))
async def buy_process(callback_query: types.CallbackQuery, state: FSMContext):
    prod_id = callback_query.data.split("_")[1]
    prod_doc = db.collection('products').document(prod_id).get()
    if not prod_doc.exists:
        await callback_query.answer("প্রোডাক্ট পাওয়া যায়নি!")
        return
    
    p = prod_doc.to_dict()
    await state.update_data(target_prod_id=prod_id, target_prod_name=p['name'], target_price=p['price'])
    
    instruction = (
        f"💳 **Payment Instruction**\n\n"
        f"Product: {p['name']}\n"
        f"Amount: {p['price']}৳\n\n"
        f"Bkash/Nagad: `01XXXXXXXXX`\n\n"
        "✅ পেমেন্ট করার পর আপনার **Transaction ID** লিখে এখানে পাঠান।"
    )
    await callback_query.message.answer(instruction, parse_mode="Markdown")
    await callback_query.answer()
    await state.set_state(UserStates.submitting_trx)

@dp.message(UserStates.submitting_trx)
async def handle_trx(message: types.Message, state: FSMContext):
    data = await state.get_data()
    trx_id = message.text
    
    # Create Order in Firebase
    order_data = {
        "user_id": message.from_user.id,
        "user_name": message.from_user.full_name,
        "product_id": data['target_prod_id'],
        "product_name": data['target_prod_name'],
        "price": data['target_price'],
        "trx_id": trx_id,
        "status": "pending"
    }
    new_order = db.collection('orders').add(order_data)
    order_id = new_order[1].id

    await message.answer("⏳ পেমেন্ট যাচাই হচ্ছে... এডমিন অ্যাপ্রুভ করলে আপনি প্রোডাক্ট পাবেন।")
    
    # Notify Admin
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"app_{order_id}"),
         InlineKeyboardButton(text="❌ Reject", callback_data=f"rej_{order_id}")]
    ])
    await bot.send_message(ADMIN_ID, f"🆕 **New Order!**\n\n👤 User: {message.from_user.full_name}\n📦 Product: {data['target_prod_name']}\n💰 Price: {data['target_price']}৳\n🧾 TRX ID: {trx_id}", reply_markup=admin_kb, parse_mode="Markdown")
    await state.clear()

# --- Admin Handlers ---

@dp.callback_query(F.data.startswith("app_"))
async def admin_approve(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID: return
    order_id = callback_query.data.split("_")[1]
    
    order_ref = db.collection('orders').document(order_id)
    order = order_ref.get()
    if not order.exists: return
    
    order_data = order.to_dict()
    # Get product content
    prod_doc = db.collection('products').document(order_data['product_id']).get()
    content = prod_doc.to_dict()['content']

    # Update Order Status
    order_ref.update({"status": "approved"})

    # Notify User
    await bot.send_message(order_data['user_id'], f"✅ **Payment Confirmed!**\n\n📦 Product: {order_data['product_name']}\n🔗 Content: `{content}`", parse_mode="Markdown")
    await callback_query.message.edit_text(f"✅ Order {order_id} Approved!")

@dp.callback_query(F.data.startswith("rej_"))
async def admin_reject(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID: return
    order_id = callback_query.data.split("_")[1]
    order_ref = db.collection('orders').document(order_id)
    order = order_ref.get()
    if not order.exists: return
    
    order_ref.update({"status": "rejected"})
    await bot.send_message(order['user_id'], "❌ আপনার পেমেন্টটি রিজেক্ট করা হয়েছে। সাপোর্ট টিমে যোগাযোগ করুন।")
    await callback_query.message.edit_text(f"❌ Order {order_id} Rejected!")

@dp.message(F.text == "➕ Add Category")
async def add_cat_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("নতুন ক্যাটাগরির নাম লিখুন:")
    await state.set_state(AdminStates.add_cat_name)

@dp.message(AdminStates.add_cat_name)
async def save_cat(message: types.Message, state: FSMContext):
    db.collection('categories').add({'name': message.text})
    await message.answer("✅ ক্যাটাগরি তৈরি হয়েছে!", reply_markup=admin_main_menu())
    await state.clear()

@dp.message(F.text == "➕ Add Product")
async def add_prod_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("প্রোডাক্টের নাম লিখুন:")
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def proc_p_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("দাম লিখুন (শুধু সংখ্যা):")
    await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def proc_p_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("ক্যাটাগরির ID লিখুন (অথবা ক্যাটাগরি লিস্ট দেখতে 'List' লিখুন):")
    await state.set_state(AdminStates.add_prod_cat_id)

@dp.message(AdminStates.add_prod_cat_id)
async def proc_p_cat(message: types.Message, state: FSMContext):
    await state.update_data(cat_id=message.text)
    await message.answer("ডেলিভারি কন্টেন্ট (লিঙ্ক বা টেক্সট) লিখুন:")
    await state.set_state(AdminStates.add_prod_content)

@dp.message(AdminStates.add_prod_content)
async def proc_p_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    db.collection('products').add({
        'name': data['name'],
        'price': data['price'],
        'category_id': data['cat_id'],
        'content': message.text
    })
    await message.answer("✅ প্রোডাক্ট যোগ হয়েছে!", reply_markup=admin_main_menu())
    await state.clear()

@dp.message(F.text == "📝 Change Welcome")
async def admin_welcome_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("নতুন ওয়েলকাম মেসেজটি লিখুন:")
    await state.set_state(AdminStates.set_welcome)

@dp.message(AdminStates.set_welcome)
async def save_welcome(message: types.Message, state: FSMContext):
    db.collection('settings').document('welcome').set({'text': message.text})
    await message.answer("✅ ওয়েলকাম মেসেজ আপডেট হয়েছে!", reply_markup=admin_main_menu())
    await state.clear()

@dp.message(F.text == "🔙 Back to User Menu")
async def back_to_user(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Switching to User View...", reply_markup=user_main_menu())

# --- Render Health Check Server ---
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is Alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    await web.TCPSite(runner, '0.0.0.0', port).start()

async def main():
    await initialize_db()
    await start_web_server()
    print("🚀 Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import traceback  # এটি এরর দেখার জন্য প্রয়োজন
    try:
        asyncio.run(main())
    except Exception as e:
        print("❌ --- CRITICAL ERROR FOUND --- ❌")
        traceback.print_exc()  # এটি আসল এররটি লগে প্রিন্ট করবে
        print("---------------------------------")
